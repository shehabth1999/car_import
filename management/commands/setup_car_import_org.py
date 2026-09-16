# -*- coding: utf-8 -*-
"""Put the organisation in place: groups with people in them, and branches.

This exists because of something found on the live tenant: the six security
groups were created, every permission and access rule pointed at them, and
**not one user belonged to any of them**. Every rule applied to nobody. A
security model with empty groups is not a security model.

    uv run python manage.py setup_car_import_org --report
    uv run python manage.py setup_car_import_org --assign owner@example.com=management
    uv run python manage.py setup_car_import_org --branches
    uv run python manage.py setup_car_import_org --csv people.csv --dry-run
    uv run python manage.py setup_car_import_org --csv people.csv

The CSV is the client's list: `name, email, phone, group` per line, group one of
sales_agent, sales_manager, operations, germany_team, showroom, management. A
person who has no user yet gets one with **no password** — they set it through
the reset link — and lands in the group; an existing user only joins the group.

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
        parser.add_argument('--csv', metavar='FILE',
                            help="name,email,phone,group per line — create users and assign")
        parser.add_argument('--dry-run', action='store_true',
                            help="With --csv: report what would happen, write nothing")

    def handle(self, *args, **options):
        from modules.base.models.user import User
        from modules.base.models import Group

        if options['assign']:
            self._assign(User, Group, options['assign'])
        if options['csv']:
            self._from_csv(User, Group, options['csv'], options['dry_run'])
        if options['branches']:
            self._branches()
        if options['report'] or not (options['assign'] or options['branches'] or options['csv']):
            self._report(User, Group)

    # ------------------------------------------------------------------
    def _from_csv(self, User, Group, path, dry_run):
        import csv
        from django.core.exceptions import ValidationError
        from django.core.management.base import CommandError
        from django.db import transaction
        try:
            handle = open(path, encoding='utf-8-sig', newline='')
        except OSError as exc:
            raise CommandError(f'Cannot read {path}: {exc}')
        self.stdout.write(self.style.NOTICE('\nPeople from ' + path))
        landed, problems = [], []
        users = User.all_objects if hasattr(User, 'all_objects') else User.objects
        with handle, transaction.atomic():
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                name = (row.get('name') or '').strip()
                email = (row.get('email') or '').strip().lower()
                short = (row.get('group') or '').strip()
                technical_name = short if short.startswith('car_import.') else f'car_import.{short}'
                if not (name and email and short):
                    problems.append((line_no, name or email or '?', 'name, email and group are required'))
                    continue
                if technical_name not in GROUPS:
                    problems.append((line_no, email, f'{short} is not a car_import group'))
                    continue
                group = Group.objects.filter(technical_name=technical_name).first()
                if group is None:
                    problems.append((line_no, email, f'{technical_name} missing — run sync_all'))
                    continue
                user = users.filter(email__iexact=email).first()
                created = False
                if user is None:
                    # No password on purpose: nobody types a colleague's password
                    # into a spreadsheet. The reset link is how they get in.
                    # The seat entitlement can refuse here (5/5 on the test
                    # tenant); that is a row to report, not a reason to stop.
                    try:
                        with transaction.atomic():
                            user = User.objects.create_user(email, None, name=name)
                    except ValidationError as exc:
                        problems.append((line_no, email, '; '.join(exc.messages)))
                        continue
                    created = True
                user.groups.add(group)
                landed.append((line_no, email, technical_name,
                               'created, no password yet' if created else 'existing user'))
            if dry_run:
                transaction.set_rollback(True)
        for line_no, email, technical_name, how in landed:
            self.stdout.write(self.style.SUCCESS(f'  line {line_no}: {email} -> {technical_name}  ({how})'))
        for line_no, who, why in problems:
            self.stdout.write(self.style.ERROR(f'  line {line_no}: {who}: {why}'))
        if dry_run:
            self.stdout.write(self.style.WARNING('  dry run — nothing written'))

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
        # A branch belongs to a company — Branch.save() runs full_clean and
        # refuses a null one. Use the tenant's own company rather than inventing
        # one: standing up a legal entity has tax and contract consequences and
        # is not a decision a setup command should take.
        company = None
        try:
            from modules.base.models import Company
            company = Company.objects.order_by('id').first()
        except Exception:
            pass
        if company is None:
            self.stdout.write(self.style.ERROR(
                '  No company on this instance — create one first, then re-run. '
                'A branch cannot exist without one.'))
            return

        for code, name, note in BRANCHES:
            values = {'company': company}
            if hasattr(Branch, 'code'):
                values['code'] = code
            row, created = Branch.objects.get_or_create(name=name, defaults=values)
            self.stdout.write(f'  {name}: {"created" if created else "already there"}  '
                              f'(company: {company.name})  — {note}')
