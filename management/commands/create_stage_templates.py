# -*- coding: utf-8 -*-
"""Create the stage messages as DRAFT WhatsApp templates on one number.

    uv run python manage.py create_stage_templates                 # list the numbers
    uv run python manage.py create_stage_templates --account 4 --dry-run
    uv run python manage.py create_stage_templates --account 4

It writes drafts and links each to its stage. **It never submits anything to
WhatsApp**: a draft goes to Meta only when somebody presses Review on the
template's own screen (WhatsApp → Templates). Run it again after a stage's
wording changes and the drafts follow; a template that has already been
submitted is left alone.

A template belongs to one number. For a second number run it again with that
`--account` and `--no-link` — a stage points at one template, and the first
set keeps it.
"""
from django.core.management.base import BaseCommand

OUTCOME = {
    'created': 'draft created',
    'updated': 'draft rewritten',
    'would_create': 'would create a draft',
    'would_update': 'would rewrite the draft',
    'submitted_untouched': 'ALREADY SUBMITTED — left as it is',
    'refused': 'REFUSED',
    'no_text': 'no message text on the stage — skipped',
}


class Command(BaseCommand):
    help = "Create the stage messages as draft WhatsApp templates (never submits them)"

    def add_arguments(self, parser):
        parser.add_argument('--account', type=int, default=None,
                            help="The WhatsApp number's id. Without it, the numbers are listed")
        parser.add_argument('--prefix', default='ka', help="Template name prefix (default: ka)")
        parser.add_argument('--no-link', action='store_true',
                            help="Do not point the stages at these templates")
        parser.add_argument('--dry-run', action='store_true', help="Show what would be written")

    def handle(self, *args, **options):
        from car_import.services import stage_templates
        from modules.whatsapp.models import WhatsAppAccount, WhatsAppTemplate

        if not options['account']:
            self.stdout.write('WhatsApp numbers on this system (pass one with --account):')
            for account in WhatsAppAccount.objects.order_by('id'):
                count = WhatsAppTemplate.objects.filter(whatsapp_account=account).count()
                self.stdout.write(f'  {account.pk}  {account.name}  ({count} template(s))')
            return

        account = WhatsAppAccount.objects.filter(pk=options['account']).first()
        if account is None:
            self.stderr.write(self.style.ERROR(f"No WhatsApp number with id {options['account']}"))
            return

        results = stage_templates.create_drafts(
            account, prefix=options['prefix'], link=not options['no_link'], dry_run=options['dry_run'])

        self.stdout.write(self.style.NOTICE(f'\nStage templates on "{account.name}":'))
        for result in results:
            stage = result['stage']
            line = f"  {stage.sequence:>3}  {result.get('name', stage.code):<28} {OUTCOME[result['outcome']]}"
            if result.get('variables'):
                line += '  · fills: ' + ', '.join(result['variables'])
            self.stdout.write(line)
            if result.get('error'):
                self.stdout.write(self.style.ERROR(f"       {result['error']}"))
            for warning in result.get('warnings') or []:
                self.stdout.write(self.style.WARNING(f'       check: it {warning}'))

        written = sum(1 for r in results if r['outcome'] in ('created', 'updated'))
        self.stdout.write(self.style.SUCCESS(
            f"\n{written} draft(s) written." if not options['dry_run'] else '\nDry run: nothing written.'))
        self.stdout.write('Nothing was submitted to WhatsApp. Each one stays a draft until somebody '
                          'presses Review on it.')
