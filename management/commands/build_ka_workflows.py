# -*- coding: utf-8 -*-
"""
Build the KA Sales agent workflow directly on a server.

Idempotent: re-running replaces the graph wholesale, so the script — not the
canvas — stays the source of truth. Nodes are saved one by one (never
`queryset.update`) because the compile cache is invalidated in `post_save`; a
bulk update would leave every worker running the old graph.

    uv run python manage.py build_ka_workflows --voice aya
    uv run python manage.py build_ka_workflows --voice aya --release <whatsapp_account_id>
    uv run python manage.py build_ka_workflows --voice aya --canary <partner_id>
    uv run python manage.py build_ka_workflows --rollback
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create or refresh the KA Sales workflow, and optionally point a WhatsApp account at it"

    def add_arguments(self, parser):
        parser.add_argument('--voice', default='aya', choices=['aya', 'ramy', 'social'],
                            help="Which agent's voice this copy speaks in")
        parser.add_argument('--owner', type=int, default=None,
                            help="User id that owns the workflow (defaults to the first superuser)")
        parser.add_argument('--release', type=int, default=None,
                            help="WhatsApp account id to attach the workflow to, and switch AI on")
        parser.add_argument('--canary', type=int, action='append', default=None,
                            help="Partner id to route through this workflow only (repeatable)")
        parser.add_argument('--rollback', action='store_true',
                            help="Detach the workflow from every account and partner — humans handle everything")
        parser.add_argument('--dry-run', action='store_true', help="Report what would change, write nothing")

    @transaction.atomic
    def handle(self, *args, **options):
        from car_import.workflows import ka_sales_definition as definition
        from modules.aistudio.models import LLMModel, ToolDefinition, WorkflowDefinition, WorkflowEdge, WorkflowNode

        voice = options['voice']
        payload = definition.workflow_payload(voice)
        name = payload.pop('name')

        if options['rollback']:
            return self._rollback(name, options['dry_run'])

        owner = self._owner(options['owner'])
        tools = self._tool_ids(ToolDefinition, definition.TOOL_NAMES)
        model_id, model_name = self._first_model(LLMModel, definition.LLM_MODEL_CANDIDATES)
        backup_id, backup_name = self._first_model(LLMModel, definition.BACKUP_LLM_MODEL_CANDIDATES)

        if model_id is None:
            wanted = ', '.join(name for name, _p in definition.LLM_MODEL_CANDIDATES)
            raise CommandError(
                f"None of these models is active on this instance: {wanted}. "
                f"Run `setup_llm_providers`, or edit LLM_MODEL_CANDIDATES in ka_sales_definition.py."
            )
        self.stdout.write(f"Model: {model_name}")
        if backup_id is None:
            self.stdout.write(self.style.WARNING(
                "No backup model resolved — set one in the node after this runs. "
                "Without a backup, a provider outage becomes the agent's reply text."
            ))
        else:
            self.stdout.write(f"Backup model: {backup_name}")

        if options['dry_run']:
            self.stdout.write(f"Would build '{name}' with {len(tools)} tool(s), model {model_id}.")
            return

        workflow, created = WorkflowDefinition.objects.update_or_create(
            name=name,
            defaults=dict(payload, owner=owner, is_active=True, error_message=definition.ERROR_MESSAGE),
        )

        workflow.nodes.all().delete()
        workflow.edges.all().delete()

        for node in definition.nodes(voice):
            config = dict(node['configuration'])
            if node['node_id'] == 'sales_agent':
                config['llm_model_id'] = model_id
                config['backup_llm_model_id'] = backup_id
                config = self._attach_knowledge(config)
                config['selected_tools'] = [
                    {'tool_id': tool_id, 'ask_human': False, 'store': True}
                    for tool_id in tools.values() if tool_id
                ]
            WorkflowNode.objects.create(workflow=workflow, **dict(node, configuration=config))

        for edge in definition.EDGES:
            WorkflowEdge.objects.create(workflow=workflow, **edge)

        missing = [name_ for name_, pk in tools.items() if not pk]
        if missing:
            self.stdout.write(self.style.WARNING(
                "These tools are not registered yet — run `sync_tools --app car_import` and re-run: "
                + ', '.join(missing)
            ))

        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Refreshed'} '{name}' "
            f"({workflow.nodes.count()} nodes, {workflow.edges.count()} edges)."
        ))

        if options['canary']:
            self._canary(workflow, options['canary'])
        if options['release']:
            self._release(workflow, options['release'])

        self.stdout.write(
            "\nBefore any customer sees it: run the verification below, confirm the AI quota, and keep "
            "`handled_by_ai` off until the evals pass.\n"
            "  uv run python manage.py shell -c \"from modules.aistudio.models import WorkflowDefinition as W; "
            "w=W.objects.get(name='" + name + "'); "
            "ns={n.node_id for n in w.nodes.all()}; ts={e.target_node_id for e in w.edges.all()}; "
            "print('entry:', ns-ts)\""
        )

    # ── helpers ─────────────────────────────────────────────────────────────
    def _owner(self, owner_id):
        from modules.base.models.user import User

        if owner_id:
            owner = User.all_objects.filter(pk=owner_id).first()
            if owner is None:
                raise CommandError(f"No user with id {owner_id}")
            return owner
        owner = User.all_objects.filter(is_superuser=True).order_by('pk').first()
        if owner is None:
            raise CommandError("No superuser to own the workflow — pass --owner <user_id>")
        return owner

    def _attach_knowledge(self, config):
        """Point the retriever at the approved-answers collection, or drop it.

        A node that names a collection which is not indexed is a node whose
        every turn fails on the retriever. Missing is better than broken, and
        the build says which one it did.
        """
        from modules.aistudio.models import Collection

        from car_import.workflows import ka_sales_definition as definition

        block = config.get('rag_retriever')
        if not block:
            return config
        row = Collection.objects.filter(name=definition.KNOWLEDGE_COLLECTION_NAME,
                                        is_indexed=True).first()
        if row is None:
            self.stdout.write(self.style.WARNING(
                f"Knowledge collection '{definition.KNOWLEDGE_COLLECTION_NAME}' is not indexed — "
                "run `build_ka_knowledge` and re-run. The agent is built WITHOUT the retriever."))
            config.pop('rag_retriever', None)
            return config
        for entry in block.get('collections', []):
            entry['collection_id'] = row.pk
        self.stdout.write(f"Knowledge: '{row.name}' (id {row.pk})")
        return config

    def _tool_ids(self, ToolDefinition, names):
        rows = dict(ToolDefinition.objects.filter(name__in=names, is_active=True).values_list('name', 'pk'))
        return {name: rows.get(name) for name in names}

    def _model_id(self, LLMModel, name, provider):
        qs = LLMModel.objects.filter(name=name, is_active=True)
        if provider:
            # iexact: providers are seeded lower-case ('anthropic', 'openai'),
            # and an exact match on 'Anthropic' silently found nothing — the
            # build then reported the model as missing when it was right there.
            qs = qs.filter(provider__name__iexact=provider)
        return qs.values_list('pk', flat=True).first()

    def _first_model(self, LLMModel, candidates):
        """The first candidate this instance actually has, as (id, name)."""
        for name, provider in candidates:
            pk = self._model_id(LLMModel, name, provider)
            if pk is not None:
                return pk, name
        return None, None

    def _canary(self, workflow, partner_ids):
        from modules.base.models import Partner

        updated = 0
        for partner in Partner.all_objects.filter(pk__in=partner_ids):
            if hasattr(partner, 'workflow'):
                partner.workflow = workflow
                partner.save(update_fields=['workflow'])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Canary: {updated} partner(s) routed to this workflow."))

    def _release(self, workflow, account_id):
        from modules.whatsapp.models import WhatsAppAccount

        account = WhatsAppAccount.objects.filter(pk=account_id).first()
        if account is None:
            raise CommandError(f"No WhatsApp account with id {account_id}")
        account.workflow = workflow
        account.handled_by_ai = True
        account.save(update_fields=['workflow', 'handled_by_ai'])
        self.stdout.write(self.style.SUCCESS(
            f"Released on WhatsApp account {account_id}. New conversations will be handled by the AI."
        ))

    def _rollback(self, name, dry_run):
        from modules.aistudio.models import WorkflowDefinition
        from modules.base.models import Partner
        from modules.whatsapp.models import WhatsAppAccount

        workflow = WorkflowDefinition.objects.filter(name=name).first()
        if workflow is None:
            self.stdout.write("Nothing to roll back.")
            return
        if dry_run:
            self.stdout.write(f"Would detach '{name}' from every account and partner.")
            return

        accounts = WhatsAppAccount.objects.filter(workflow=workflow)
        for account in accounts:
            account.workflow = None
            account.handled_by_ai = False
            account.save(update_fields=['workflow', 'handled_by_ai'])

        partners = Partner.all_objects.filter(workflow=workflow) if hasattr(Partner, 'workflow') else []
        for partner in partners:
            partner.workflow = None
            partner.save(update_fields=['workflow'])

        self.stdout.write(self.style.SUCCESS(
            "Rolled back: humans handle every conversation again. The workflow itself is kept."
        ))
