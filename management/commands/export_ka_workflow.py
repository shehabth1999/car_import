# -*- coding: utf-8 -*-
"""
Write the KA Sales workflow as an AI Studio bundle you can import elsewhere.

Use it when the target server is one you cannot run commands on: export here,
import through AI Studio → Workflows → Import there. Tools and models are
carried by name and resolved against the target instance.

    uv run python manage.py export_ka_workflow
    uv run python manage.py export_ka_workflow --from-database
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Export the KA Sales workflow as an importable AI Studio bundle (.json)"

    def add_arguments(self, parser):
        parser.add_argument('--out', default=None, help="Where to write the file")
        parser.add_argument('--from-database', action='store_true',
                            help="Export the live workflow row instead of the definition in code")

    def handle(self, *args, **options):
        from car_import.workflows import ka_sales_definition as definition

        out = options['out'] or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(definition.__file__)))),
            'car_import', 'workflows', 'ka_sales.bundle.json',
        )

        if options['from_database']:
            import json

            from modules.aistudio.models import WorkflowDefinition
            from modules.aistudio.services.workflow_portability import build_bundle

            name = definition.workflow_payload()['name']
            workflow = WorkflowDefinition.objects.filter(name=name).first()
            if workflow is None:
                raise CommandError(f"No workflow named '{name}' on this instance. Build it first.")
            payload = build_bundle(workflow)
            with open(out, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        else:
            definition.write_bundle(out, exported_at=timezone.now().isoformat())

        self.stdout.write(self.style.SUCCESS(f"Wrote {out}"))
        self.stdout.write(
            "Import it on the target server: AI Studio → Workflows → Import → choose this file.\n"
            "Then open the agent node and confirm the model and the backup model resolved."
        )
