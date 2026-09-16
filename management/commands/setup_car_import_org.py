# -*- coding: utf-8 -*-
"""Put the organisation in place: groups with people in them, and branches.

This exists because of something found on the live tenant: the six security
groups were created, every permission and access rule pointed at them, and
**not one user belonged to any of them**. Every rule applied to nobody. A
security model with empty groups is not a security model.

    uv run python manage.py setup_car_import_org --report
    uv run python manage.py setup_car_import_org --assign owner@example.com=management
    uv run python manage.py setup_car_import_org --branches

Nobody is assigned automatically. Who sees a customer's national ID is the
client's decision, not a default.
"""
from django.core.management.base import BaseCommand

GROUPS = [
    'car_import.sales_agent',
    'car_import.sales_manager',
    'car_import.operations',
    'car_import.germany_team',
    'car_import.showroom',
    'car_import.management',
]

#: The client's real structure: K&T issues the contracts, the GmbH buys the
#: cars, and the showroom is where customers turn up.
BRANCHES = [
    ('kt', 'K&T — كيه اند تي', 'The contract issuer and marketing agent'),
    ('gmbh', 'Khaled Automobile GmbH', 'The German buying arm'),
    ('showroom', 'المعرض', 'Where customers come and cars are handed over'),
]


class Command(BaseCommand):
    help = "Report or fix the car_import group membership, and create the branches"

    def add_arguments(self, parser):
        parser.add_argument('--report', action='store_true',
                            help="Who is in which group (the default)")
        parser.add_argument('--assign', action='append', default=[],
                            metavar='EMAIL=GROUP',
                            help="e.g. --assign ramy@example.com=sales_manager (repeatable)")
        parser.add_argument('--branches', action='store_true',
                            help="Create the three branches if they are missing")

    def handle(self, *args, **options):
        from modules.base.models.user import User
        from modules.base.models import Group

        if options['assign']:
            self._assign(User, Group, options['assign'])
        if options['branches']:
            self._branches()
        if options['report'] or not (options['assign'] or options['branches']):
            self._report(User, Group)

    # ------------------------------------------------------------------
    def _report(self, User, Group):
        self.stdout.write(self.style.NOTICE('\nGroup membership'))
        empty = []
        for technical_name in GROUPS:
            group = Group.objects.filter(technical_name=technical_name).first()
            if group is None:
                self.stdout.write(self.style.ERROR(f'  {technical_name:<32} MISSING — run sync_all'))
                continue
            members = list(User.objects.filter(groups=group, is_active=True)
                           .values_list('email', flat=True))
            if members:
                self.stdout.write(f'  {technical_name:<32} {len(members)}: {", ".join(members[:4])}')
            else:
                empty.append(technical_name)
                self.stdout.write(self.style.WARNING(f'  {technical_name:<32} nobody'))

        if empty:
            self.stdout.write(self.style.ERROR(
                f'\n{len(empty)} group(s) are empty. Every permission and every access rule that '
                f'names them applies to NOBODY until somebody is in them.'))
            self.stdout.write('Assign with:  manage.py setup_car_import_org '
                              '--assign person@example.com=sales_agent')
        else:
            self.stdout.write(self.style.SUCCESS('\nEvery group has at least one member.'))

    # ------------------------------------------------------------------
    def _assign(self, User, Group, pairs):
        self.stdout.write(self.style.NOTICE('\nAssigning'))
        for pair in pairs:
            if '=' not in pair:
                self.stdout.write(self.style.ERROR(f'  {pair}: expected EMAIL=GROUP'))
                continue
            email, _, short = pair.partition('=')
            technical_name = short if short.startswith('car_import.') else f'car_import.{short}'
            if technical_name not in GROUPS:
                self.stdout.write(self.style.ERROR(
                    f'  {short}: not a car_import group. One of: '
                    f'{", ".join(g.split(".")[1] for g in GROUPS)}'))
                continue
            user = User.objects.filter(email__iexact=email.strip()).first()
            group = Group.objects.filter(technical_name=technical_name).first()
            if user is None:
                self.stdout.write(self.style.ERROR(f'  {email}: no such user'))
                continue
            if group is None:
                self.stdout.write(self.style.ERROR(f'  {technical_name}: missing — run sync_all'))
                continue
            user.groups.add(group)
            self.stdout.write(self.style.SUCCESS(f'  {user.email} -> {technical_name}'))

    # ------------------------------------------------------------------
    def _branches(self):
        try:
            from modules.base.models import Branch
        except Exception:
            self.stdout.write(self.style.WARNING('\nNo Branch model on this instance; skipped.'))
            return
        self.stdout.write(self.style.NOTICE('\nBranches'))
        for code, name, note in BRANCHES:
            row, created = Branch.objects.get_or_create(
                name=name, defaults={'code': code} if hasattr(Branch, 'code') else {})
            self.stdout.write(f'  {name}: {"created" if created else "already there"}  — {note}')
