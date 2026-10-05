# -*- coding: utf-8 -*-
"""Load the client's Odoo leads, with their chatter, from an export folder.

    uv run python manage.py import_odoo_leads /path/to/export --dry-run --limit 300
    uv run python manage.py import_odoo_leads /path/to/export

The folder holds what the Odoo export wrote, plain or gzipped (`.json.gz`):
`crm.lead`, `crm.stage`, `crm.tag`, `utm.source`, `utm.medium`, `utm.campaign`,
`users`, and for the history `chatter.messages`, `chatter.tracking`,
`chatter.attachments`, `chatter.fields`.

Three things decide how this is written:

* **Nothing may reach a customer.** Everything goes in with `bulk_create`, so no
  save hook, signal, notification or broadcast runs. And the leads keep their
  OWN Odoo stages: the follow-up engine (`crm.tasks.scan_followup_executions`)
  messages idle chats whose customer's newest lead sits in a stage that has a
  rule, and the tenant's rules are on the tenant's stages. A lead in an Odoo
  stage can never arm one. Mapping "New Lead" onto «جديد» would have queued
  WhatsApp follow-ups for every old customer who has a chat here.
* **Dates are the record.** `created_at` is what makes a lead the newest one for
  its customer, and what orders the chatter — so the Odoo dates are kept, not
  today's.
* **It can be run again.** Every row carries `key = odoo_…_<odoo id>`; a second
  run adds only what is missing.

The files Odoo holds against the leads (10 GB of screenshots) are not loaded:
a note that had some says how many and what they were called, and keeps their
Odoo ids in `headers` so they can be attached later.
"""
import gzip
import json
import re
from collections import defaultdict
from datetime import datetime, timezone as dt_timezone
from html import escape
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

BATCH = 1000

#: Odoo stages come after the tenant's own in every list and on the kanban.
STAGE_OFFSET = 100
#: Final by their name. Not `is_lost`: that would demand a lost reason on every edit.
CLOSED_STAGE_WORDS = ('lost', 'junk')

LEAD_TYPE_TAGS = {'hot': 'Hot Lead', 'cold': 'Cold Lead', 'potential': 'Potential Lead'}
#: The salesperson Odoo parked unowned leads on. Not a person, so not a user here.
REASSIGN_USER = 'To re-assign'
PROGRAM_BY_TAG = {'personal import': 'personal', 'initiatives': 'initiative'}
#: Odoo used these as "brands" for leads that named no car.
NOT_A_BRAND = {'unspecified', 'available cars in egypt', 'electric cars'}

#: Odoo field name -> ours, for the change history.
TRACKED_FIELDS = {
    'stage_id': 'stage', 'user_id': 'assigned_to', 'team_id': 'team', 'partner_id': 'partner',
    'email_from': 'email', 'phone': 'phone', 'contact_name': 'contact_name',
    'partner_name': 'partner_name', 'active': 'active',
}
#: (Odoo type, Odoo subtype) -> (our type, our subtype, internal)
MESSAGE_KINDS = {
    ('comment', 'Note'): ('comment', 'Note', True),
    ('comment', 'Discussions'): ('comment', 'Comment', False),
    ('notification', 'Stage Changed'): ('notification', 'Status Change', True),
    ('notification', 'Opportunity Won'): ('notification', 'Status Change', True),
    ('notification', 'Opportunity Lost'): ('notification', 'Status Change', True),
    ('notification', 'Opportunity Restored'): ('notification', 'Status Change', True),
    ('notification', 'Opportunity Created'): ('notification', 'Record Creation', True),
    ('notification', 'Activities'): ('notification', 'Activity Reminder', True),
    ('notification', 'Note'): ('notification', 'Field Change', True),
}
EMPTY_BODIES = {'', '<p><br></p>', '<p></p>', '<br>'}
EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def clean_label(text):
    """Odoo labels carry no-break spaces and stretched letters («مرحلــــة»)."""
    return re.sub(r'\s+', ' ', (text or '').replace('\xa0', ' ').replace('ـ', '')).strip()


def label_of(pair):
    return pair[1] if isinstance(pair, (list, tuple)) and len(pair) == 2 else ''


def id_of(pair):
    return pair[0] if isinstance(pair, (list, tuple)) and len(pair) == 2 else None


def when(text):
    """Odoo writes naive UTC."""
    if not text:
        return None
    try:
        return datetime.strptime(text[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=dt_timezone.utc)
    except ValueError:
        return None


def phone_key(*candidates):
    """Digits with the country code, the way the channels store a number here
    (201012345678). Empty when there is nothing usable to match a chat on."""
    for candidate in candidates:
        digits = re.sub(r'\D', '', candidate or '')
        if digits.startswith('00'):
            digits = digits[2:]
        if len(digits) > 15:                      # two numbers typed into one box: the first
            digits = digits[:12] if digits.startswith('20') else digits[:11]
        if len(digits) == 11 and digits.startswith('01'):
            digits = '20' + digits[1:]            # an Egyptian mobile written the local way
        elif len(digits) == 10 and digits.startswith('1'):
            digits = '20' + digits
        if 8 <= len(digits) <= 15:
            return digits
    return ''


def chunks(items, size=BATCH):
    for start in range(0, len(items), size):
        yield items[start:start + size]


class Command(BaseCommand):
    help = "Load the Odoo lead export (leads, stages, tags, sources, chatter) — safe to re-run"

    def add_arguments(self, parser):
        parser.add_argument('folder', help="Folder holding the exported .json / .json.gz files")
        parser.add_argument('--limit', type=int, default=0, help="Only the first N leads (and their chatter)")
        parser.add_argument('--dry-run', action='store_true', help="Do everything, then roll it all back")
        parser.add_argument('--no-contacts', action='store_true',
                            help="Do not create a contact for a lead whose phone matches nobody here")
        parser.add_argument('--no-chatter', action='store_true', help="Leads only")
        parser.add_argument('--rewrite-chatter', action='store_true',
                            help="Also rewrite the text of messages loaded by an earlier run")

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        self.folder = Path(options['folder'])
        if not self.folder.is_dir():
            raise CommandError(f'{self.folder} is not a folder')
        self.report = defaultdict(int)
        self.rewrite = options['rewrite_chatter']
        with transaction.atomic():
            self._run(options)
            if options['dry_run']:
                transaction.set_rollback(True)
        for label in sorted(self.report):
            self.stdout.write(f'  {label}: {self.report[label]}')
        self.stdout.write(self.style.WARNING('dry run — nothing written') if options['dry_run']
                          else self.style.SUCCESS('done'))

    def _load(self, name, required=True):
        for candidate in (self.folder / f'{name}.json', self.folder / f'{name}.json.gz'):
            if candidate.exists():
                opener = gzip.open if candidate.suffix == '.gz' else open
                with opener(candidate, 'rt', encoding='utf-8') as handle:
                    return json.load(handle)
        if required:
            raise CommandError(f'{name}.json(.gz) is missing from {self.folder}')
        return []

    # ------------------------------------------------------------------
    def _run(self, options):
        from django.apps import apps
        from modules.base.models import Company
        from car_import.services import sales_flow

        self.Lead = apps.get_model('crm', 'Lead')
        self.company = Company.objects.order_by('id').first()
        self.branch = sales_flow.default_branch()
        if self.company is None or self.branch is None:
            raise CommandError('This instance has no company or no default branch.')

        leads = sorted(self._load('crm.lead'), key=lambda row: row['id'])
        if options['limit']:
            leads = leads[:options['limit']]
        self.report['leads in the export'] = len(leads)

        stages = self._stages()
        tags = self._tags()
        sources, mediums, campaigns = self._utm(leads)
        users, authors = self._people()
        contacts = self._contacts(leads, create=not options['no_contacts'])
        lead_pks = self._leads(leads, stages, tags, sources, mediums, campaigns, users, contacts)
        if not options['no_chatter']:
            self._chatter(leads, lead_pks, authors)

    # ── lists ─────────────────────────────────────────────────────────
    def _keyed(self, model, prefix):
        return dict(model._base_manager.filter(key__startswith=prefix).values_list('key', 'pk'))

    def _stages(self):
        """Odoo's stages as stages of their own, after the tenant's."""
        from django.apps import apps
        Stage = apps.get_model('crm', 'Stage')
        have = self._keyed(Stage, 'odoo_crm_stage_')
        new = []
        for row in self._load('crm.stage'):
            key = f"odoo_crm_stage_{row['id']}"
            if key in have:
                continue
            name = clean_label(row['name'])[:100]
            won = bool(row.get('is_won'))
            new.append(Stage(
                key=key, name=name, company=self.company, sequence=STAGE_OFFSET + int(row.get('sequence') or 0),
                fold=bool(row.get('fold')), is_won=won,
                is_closed=won or any(word in name.lower() for word in CLOSED_STAGE_WORDS)))
        Stage._base_manager.bulk_create(new)
        self.report['stages created'] = len(new)
        have = self._keyed(Stage, 'odoo_crm_stage_')
        return {int(key.rsplit('_', 1)[1]): pk for key, pk in have.items()}

    def _tags(self):
        from django.apps import apps
        Tag = apps.get_model('crm', 'Tag')
        have = self._keyed(Tag, 'odoo_')
        wanted = [(f"odoo_crm_tag_{row['id']}", clean_label(row['name'])) for row in self._load('crm.tag')]
        wanted += [(f'odoo_lead_type_{code}', name) for code, name in LEAD_TYPE_TAGS.items()]
        wanted.append(('odoo_to_reassign', REASSIGN_USER))
        new = [Tag(key=key, name=name[:100], company=self.company) for key, name in wanted if key not in have]
        Tag._base_manager.bulk_create(new)
        self.report['tags created'] = len(new)
        return self._keyed(Tag, 'odoo_')

    def _utm(self, leads):
        """Only what a lead actually points at; a name that exists here is reused."""
        from django.apps import apps
        result = []
        for name, field in (('UtmSource', 'source_id'), ('UtmMedium', 'medium_id'), ('UtmCampaign', 'campaign_id')):
            model = apps.get_model('crm', name)
            used = {id_of(lead.get(field)): clean_label(label_of(lead.get(field))) for lead in leads if lead.get(field)}
            by_name = {(row.name or '').strip().lower(): row for row in model._base_manager.all()}
            mapping, made = {}, 0
            for odoo_id, label in used.items():
                row = by_name.get(label.lower())
                if row is None:
                    row = model(name=label[:100], key=f'odoo_{name.lower()}_{odoo_id}')
                    row.save()
                    by_name[label.lower()] = row
                    made += 1
                mapping[odoo_id] = row
            self.report[f'{name} rows created'] = made
            result.append(mapping)
        return result

    def _people(self):
        """Odoo user id -> our user id, and Odoo partner id -> (our user id, name) for chatter authors."""
        from modules.base.models.user import User
        ours = {(u.email or '').lower(): u.pk for u in User.objects.filter(is_active=True)}
        users, authors = {}, {}
        for row in self._load('users'):
            mine = ours.get((row.get('login') or '').strip().lower())
            if row.get('name') == REASSIGN_USER:
                mine = None
            users[row['id']] = mine
            if row.get('partner_id'):
                authors[id_of(row['partner_id'])] = (mine, clean_label(row.get('name')))
        self.report['Odoo users with an account here'] = sum(1 for pk in users.values() if pk)
        return users, authors

    # ── contacts ──────────────────────────────────────────────────────
    def _contacts(self, leads, create=True):
        """phone -> contact pk. A returning customer has to land on the contact
        their lead is on, or the chat starts from nothing."""
        from django.apps import apps
        Partner = apps.get_model('base', 'Partner')
        known = {}
        for pk, phone, mobile in Partner._base_manager.order_by('id').values_list('pk', 'phone', 'mobile'):
            for value in (phone, mobile):
                digits = phone_key(value)
                if digits:
                    known.setdefault(digits, pk)
        self.report['contacts already here with a phone'] = len(known)

        new, seen = [], set()
        for lead in leads:
            digits = phone_key(lead.get('phone_sanitized'), lead.get('phone'), lead.get('mobile'))
            lead['_phone'] = digits
            if not digits:
                self.report['leads with no usable phone'] += 1
                continue
            if digits in known:
                self.report['leads matched to a contact already here'] += 1
                continue
            if digits in seen or not create:
                continue
            seen.add(digits)
            name = clean_label(lead.get('contact_name') or label_of(lead.get('partner_id'))
                               or lead.get('partner_name') or lead.get('name')) or digits
            email = (lead.get('email_from') or '').strip()
            new.append(Partner(key=f'odoo_phone_{digits}', name=name[:255], phone=digits,
                               email=email if EMAIL.match(email) else None))
        for batch in chunks(new):
            Partner._base_manager.bulk_create(batch)
        self.report['contacts created'] = len(new)
        for key, pk in self._keyed(Partner, 'odoo_phone_').items():
            known.setdefault(key[len('odoo_phone_'):], pk)
        return known

    # ── leads ─────────────────────────────────────────────────────────
    def _car(self, lead, cache):
        """(brand pk, model pk, words, year, colour) from Odoo's four lists."""
        from car_import.services import catalogue
        brand_name = clean_label(label_of(lead.get('inst_car_brand_id')))
        model_name = clean_label(label_of(lead.get('inst_car_model_id')))
        year = clean_label(label_of(lead.get('inst_car_model_year_id')))
        colour = clean_label(label_of(lead.get('inst_car_color_id')))
        if brand_name.lower() in NOT_A_BRAND:
            brand_name = ''
        if model_name.lower() in NOT_A_BRAND:
            model_name = ''
        slot = (brand_name, model_name)
        if slot not in cache:
            brand = catalogue.find_brand(brand_name) if brand_name else None
            car_model = catalogue.find_model(brand, model_name) if brand and model_name else None
            cache[slot] = (getattr(brand, 'pk', None), getattr(car_model, 'pk', None))
        brand_pk, model_pk = cache[slot]
        words = ' '.join(part for part in (brand_name, model_name) if part)
        return brand_pk, model_pk, words, (int(year) if re.fullmatch(r'\d{4}', year) else None), colour

    def _footer(self, lead, owner_missing):
        """What Odoo knew that has no field here, kept where the salesperson reads."""
        lines = [f"رقم Odoo: {lead['id']}"]
        for label, value in (
            ('نوع الطلب', label_of(lead.get('inst_product_type_id'))),
            ('حالة المعالجة', lead.get('processing_state')),
            ('سنة الموديل', label_of(lead.get('inst_car_model_year_id'))),
            ('المبرر', lead.get('inst_justification')),
            ('Meta ID', lead.get('meta_id')),
            ('البياع في Odoo', label_of(lead.get('user_id')) if owner_missing else ''),
        ):
            if value:
                lines.append(f'{label}: {clean_label(str(value))}')
        return '<hr><p><b>من Odoo</b><br>' + '<br>'.join(lines) + '</p>'

    def _leads(self, leads, stages, tags, sources, mediums, campaigns, users, contacts):
        from modules.crm.models.lead import ORIGIN_ORGANIC, origin_for_medium
        Lead = self.Lead
        # The Odoo dates, not today's — see the module docstring.
        for name in ('created_at', 'updated_at'):
            field = Lead._meta.get_field(name)
            field.auto_now = field.auto_now_add = False

        have = self._keyed(Lead, 'odoo_crm_lead_')
        first_stage = stages[min(stages)] if stages else None
        tag_names = {row['id']: clean_label(row['name']).lower() for row in self._load('crm.tag')}
        cars, new, links = {}, [], []
        for lead in leads:
            key = f"odoo_crm_lead_{lead['id']}"
            if key in have:
                self.report['leads already loaded'] += 1
                continue
            owner_id = id_of(lead.get('user_id'))
            owner = users.get(owner_id)
            parked = label_of(lead.get('user_id')) == REASSIGN_USER
            medium = mediums.get(id_of(lead.get('medium_id')))
            brand_pk, model_pk, words, year, colour = self._car(lead, cars)
            odoo_tags = lead.get('tag_ids') or []
            program = next((PROGRAM_BY_TAG[tag_names[t]] for t in odoo_tags if tag_names.get(t) in PROGRAM_BY_TAG), None)
            email = (lead.get('email_from') or '').strip()
            website = (lead.get('website') or '').strip()
            created = when(lead.get('create_date'))
            new.append(Lead(
                key=key, branch=self.branch, name=clean_label(lead.get('name'))[:255] or key,
                description=(lead.get('description') or '') + self._footer(lead, owner_id and not owner and not parked),
                stage_id=stages.get(id_of(lead.get('stage_id')), first_stage),
                expected_revenue=0, probability=max(0, min(100, int(round(lead.get('probability') or 0)))),
                priority=int(lead.get('priority') or 0),
                email=email if EMAIL.match(email) else '', phone=(lead['_phone'] or '')[:20],
                mobile=phone_key(lead.get('mobile'))[:20],
                contact_name=clean_label(lead.get('contact_name'))[:255],
                partner_name=clean_label(lead.get('partner_name'))[:255],
                website=website if website.startswith('http') else '',
                street=clean_label(lead.get('street'))[:255], street2=clean_label(lead.get('street2'))[:255],
                zip=clean_label(lead.get('zip'))[:20],
                expected_closing=(lead.get('date_deadline') or None), closed_date=when(lead.get('date_closed')),
                created_at=created, updated_at=when(lead.get('write_date')) or created,
                partner_id=contacts.get(lead['_phone']) if lead.get('_phone') else None,
                utm_source=sources.get(id_of(lead.get('source_id'))), utm_medium=medium,
                utm_campaign=campaigns.get(id_of(lead.get('campaign_id'))),
                lead_origin=origin_for_medium(medium) if medium else ORIGIN_ORGANIC,
                assigned_to_id=owner, is_opportunity=True, active=bool(lead.get('active', True)),
                ka_program=program, ka_brand_wanted_id=brand_pk, ka_car_model_wanted_id=model_pk,
                ka_model_wanted=words[:128] or None, ka_model_year_wanted=year, ka_colour_wanted=colour[:64] or None,
            ))
            wanted = [tags.get(f'odoo_crm_tag_{t}') for t in odoo_tags]
            wanted.append(tags.get(f"odoo_lead_type_{lead.get('inst_lead_type')}"))
            if parked:
                wanted.append(tags.get('odoo_to_reassign'))
            links.append((key, [pk for pk in wanted if pk]))
            self.report['leads with a salesperson here'] += 1 if owner else 0
            self.report['leads with the brand found in our catalogue'] += 1 if brand_pk else 0
            self.report['leads with the model found in our catalogue'] += 1 if model_pk else 0
            self.report['leads with a contact'] += 1 if new[-1].partner_id else 0

        for batch in chunks(new):
            Lead._base_manager.bulk_create(batch)
        self.report['leads created'] = len(new)

        pks = self._keyed(Lead, 'odoo_crm_lead_')
        through = Lead.tags.through
        rows = [through(lead_id=pks[key], tag_id=tag) for key, tag_pks in links for tag in dict.fromkeys(tag_pks)]
        for batch in chunks(rows, 5000):
            through.objects.bulk_create(batch, ignore_conflicts=True)
        self.report['lead tags set'] = len(rows)
        return {int(key.rsplit('_', 1)[1]): pk for key, pk in pks.items()}

    # ── chatter ───────────────────────────────────────────────────────
    def _chatter(self, leads, lead_pks, authors):
        from django.apps import apps
        from django.contrib.contenttypes.models import ContentType
        Message = apps.get_model('notifications', 'Message')
        Subtype = apps.get_model('notifications', 'MessageSubtype')
        Tracking = apps.get_model('notifications', 'Tracking')
        created_at = Message._meta.get_field('created_at')
        created_at.auto_now_add = False

        wanted_leads = {lead['id']: clean_label(lead.get('name'))[:255] for lead in leads}
        content_type = ContentType.objects.get_for_model(self.Lead)
        subtypes = {s.name: s.pk for s in Subtype.objects.all()}
        self._files = {row['id']: row.get('name') or '' for row in self._load('chatter.attachments', required=False)}
        self._field_info = {row['id']: row for row in self._load('chatter.fields', required=False)}
        tracking = self._load('chatter.tracking', required=False)
        self._changes = self._change_lines(tracking)
        have = set(Message._base_manager.filter(key__startswith='odoo_mail_message_').values_list('key', flat=True))

        new, tracked_by_message, stale = [], {}, {}
        for row in self._load('chatter.messages'):
            lead_pk = lead_pks.get(row.get('res_id'))
            if row.get('res_id') not in wanted_leads or lead_pk is None:
                continue
            key = f"odoo_mail_message_{row['id']}"
            if key in have:
                self.report['messages already loaded'] += 1
                if self.rewrite:
                    stale[key] = self.message_body(row, authors)
                continue
            kind, subtype, internal = self._kind(row)
            author_pk = authors.get(id_of(row.get('author_id')), (None, ''))[0]
            body = self.message_body(row, authors)
            attached = row.get('attachment_ids') or []
            date = when(row.get('date'))
            new.append(Message(
                key=key, content_type=content_type, object_id=str(lead_pk), res_model='crm.lead', res_id=str(lead_pk),
                record_name=wanted_leads[row['res_id']], subject=(row.get('subject') or '')[:255], body=body,
                message_type=kind, subtype_id_id=subtypes.get(subtype), author_id_id=author_pk,
                date=date, created_at=date, is_internal=internal, is_notification=(kind == 'notification'),
                headers={'odoo_id': row['id'], 'odoo_attachment_ids': attached} if attached else {'odoo_id': row['id']},
            ))
            if row.get('tracking_value_ids'):
                tracked_by_message[key] = row['id']
        for batch in chunks(new, 2000):
            Message._base_manager.bulk_create(batch)
        self.report['messages created'] = len(new)
        if stale:
            changed = []
            loaded = Message._base_manager.filter(key__startswith='odoo_mail_message_').only('id', 'key', 'body')
            for message in loaded.iterator(chunk_size=5000):
                body = stale.get(message.key)
                if body is not None and body != message.body:
                    message.body = body
                    changed.append(message)
            for batch in chunks(changed, 2000):
                Message._base_manager.bulk_update(batch, ['body'])
            self.report['messages whose text was rewritten'] = len(changed)
        if not tracked_by_message:
            return

        # The same changes as rows, for anything that reads them as data; the
        # chatter itself only draws a message's text, which already has them.
        message_pks = dict(Message._base_manager.filter(key__in=list(tracked_by_message)).values_list('key', 'pk')) \
            if len(tracked_by_message) < 5000 else self._keyed(Message, 'odoo_mail_message_')
        pk_of = {odoo_id: message_pks.get(key) for key, odoo_id in tracked_by_message.items()}
        have = set(Tracking._base_manager.filter(key__startswith='odoo_tracking_').values_list('key', flat=True))
        new, owner = [], {}
        for row in tracking:
            message_pk = pk_of.get(id_of(row.get('mail_message_id')))
            key = f"odoo_tracking_{row['id']}"
            if message_pk is None or key in have:
                continue
            odoo_name, label, old, new_value = self._change(row)
            new.append(Tracking(
                key=key, field=TRACKED_FIELDS.get(odoo_name, odoo_name)[:255] or 'field', field_desc=label,
                field_type='char', old_value_char=old, new_value_char=new_value,
                old_value_display=old, new_value_display=new_value))
            owner[key] = message_pk
        for batch in chunks(new, 2000):
            Tracking._base_manager.bulk_create(batch)
        through = Message.tracking_value_ids.through
        tracking_pks = self._keyed(Tracking, 'odoo_tracking_')
        rows = [through(message_id=owner[key], tracking_id=tracking_pks[key]) for key in owner]
        for batch in chunks(rows, 5000):
            through.objects.bulk_create(batch, ignore_conflicts=True)
        self.report['change-history rows created'] = len(new)

    @staticmethod
    def _kind(row):
        return MESSAGE_KINDS.get((row.get('message_type'), label_of(row.get('subtype_id'))),
                                 ('notification', 'System Notification', True))

    def _change(self, row):
        """One tracked change: (Odoo field name, label, old, new)."""
        info = self._field_info.get(id_of(row.get('field_id')), {})
        label = clean_label(info.get('field_description') or label_of(row.get('field_id')).split(' (')[0])[:255]
        return info.get('name') or '', label, self._shown(row, 'old', info), self._shown(row, 'new', info)

    def _change_lines(self, tracking):
        """Odoo message id -> its changes as text. The chatter here draws a
        message's text and nothing else, so "Stage: New Lead → Cold" has to be
        IN the text or the history reads as a list of empty "Stage Changed"."""
        lines = defaultdict(list)
        for row in tracking:
            _name, label, old, new_value = self._change(row)
            lines[id_of(row.get('mail_message_id'))].append(
                f'<p><b>{escape(label)}</b>: {escape(old) or "—"} → {escape(new_value) or "—"}</p>')
        return lines

    def message_body(self, row, authors):
        """The text of one Odoo message as it is shown here."""
        kind = self._kind(row)[0]
        author_pk, author_name = authors.get(id_of(row.get('author_id')),
                                             (None, clean_label(label_of(row.get('author_id')))))
        body = (row.get('body') or '').strip()
        if body in EMPTY_BODIES:
            body = ''
        body += ''.join(self._changes.get(row['id'], ()))
        attached = row.get('attachment_ids') or []
        if attached:
            names = '، '.join(name for name in (self._files.get(a, '') for a in attached[:5]) if name)
            body += f'<p>📎 مرفقات في Odoo ({len(attached)}){": " + escape(names) if names else ""}</p>'
        if not body:
            body = f'<p>{escape(label_of(row.get("subtype_id")) or "Odoo")}</p>'
        if kind == 'comment' and not author_pk and author_name:
            # Somebody with no account here wrote this; without the name it would read as the system's.
            body = f'<p><b>{escape(author_name)}</b></p>' + body
        return body

    @staticmethod
    def _shown(row, side, info):
        """One side of a change as text: Odoo keeps a relation's NAME in the char column."""
        kind = info.get('ttype')
        if kind == 'boolean':
            return 'Yes' if row.get(f'{side}_value_integer') else 'No'
        for column in ('char', 'text', 'datetime'):
            value = row.get(f'{side}_value_{column}')
            if value:
                return clean_label(str(value))[:255]
        if kind in ('integer', 'float', 'monetary'):
            value = row.get(f'{side}_value_{"integer" if kind == "integer" else "float"}')
            return '' if value in (None, False) else str(value)
        return ''
