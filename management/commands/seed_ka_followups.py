# -*- coding: utf-8 -*-
"""The follow-up cadence, as rows on the platform's own engine.

Nobody chases a silent customer today. `ka_schedule_followup` exists as a tool
the assistant may call if it feels like it; there is no schedule. The plan
asked for "day 2 nudge, day 5 nudge, day 10 close as lost" — and the CRM
already has exactly that machine: `crm.FollowupRule` with dated
`FollowupRuleMessage` lines, run by `scan_followup_executions` every two
hours, silence measured from our own last real message, closed by
`_apply_stage`. Building a second table would have meant a second scheduler,
a second WhatsApp-window check and a second close-as-lost path, all slightly
different from the ones the rest of the CRM uses.

So this seeds three rules, one per stage a KA lead sits in before it is won:

    جديد   → nudge at 2 d and 5 d, close as lost at 10 d
    مؤهل   → same cadence
    عرض    → same cadence — this is the one that matters: an offer went out
              and the customer went quiet

Wording is in the approved voice. No figures, no promises: the messages ask
one question each, because a nudge that reads like a sales pitch is the one
that gets the number blocked.

    uv run python manage.py seed_ka_followups
    uv run python manage.py seed_ka_followups --disable     # keep the rows, stop the sends
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

#: (stage name, rule name, lines) — each line is (days of silence, text).
CADENCE = [
    ('جديد', 'KA — عميل جديد سكت', [
        (2, 'أهلاً {name} 👋 حبيت أطمّن على حضرتك. لو لسه مهتم بالعربية، قولي أساعدك إزاي؟'),
        (5, 'مساء الخير {name}، لو عندك أي سؤال عن الاستيراد أو الخطوات، أنا موجودة.'),
        (10, 'هقفل الطلب مؤقتاً عشان ما أزعجش حضرتك. أول ما تحب ترجع، ابعتلي وهنكمّل من نفس النقطة 🤝'),
    ]),
    ('مؤهل', 'KA — عميل مؤهل سكت', [
        (2, 'أهلاً {name}، جاهزين نبدأ أول ما تحدد الموديل. تحب أبعتلك كام اختيار؟'),
        (5, 'مساء الخير {name}، لو فيه حاجة واقفة الطلب — ورق أو توقيت — قولي وأشوفها معاك.'),
        (10, 'هقفل الطلب مؤقتاً. لما تحب ترجع، كل اللي اتفقنا عليه محفوظ عندي 🤝'),
    ]),
    ('عرض', 'KA — عرض اتبعت والعميل سكت', [
        (2, 'أهلاً {name}، وصلك العرض؟ لو فيه أي نقطة فيه مش واضحة أشرحها لحضرتك.'),
        (5, 'مساء الخير {name}، العرض لسه ساري. لو محتاج تعديل في الموديل أو المواصفات قولي.'),
        (10, 'هقفل العرض ده عشان الأسعار في ألمانيا بتتغير. أول ما تحب نرجع، هعملك عرض بأحدث سعر 🤝'),
    ]),
]

LOST_STAGE = 'خاسر'
LOST_REASON = 'لم يتخذ قرار'
GRACE_DAYS = 3


class Command(BaseCommand):
    help = "Seed the KA follow-up cadence on crm.FollowupRule (2 d, 5 d, lost at 10 d)"

    def add_arguments(self, parser):
        parser.add_argument('--disable', action='store_true',
                            help="Keep the rows but switch them off")

    @transaction.atomic
    def handle(self, *args, **options):
        from modules.crm.models.followup import FollowupRule, FollowupRuleMessage
        from modules.crm.models.lead import LostReason, Stage

        lost_stage = Stage.objects.filter(is_lost=True).order_by('sequence').first()
        if lost_stage is None:
            self.stderr.write('No lost stage on this tenant; nothing seeded.')
            return
        lost_reason, _ = LostReason.objects.get_or_create(name=LOST_REASON)

        made, updated = 0, 0
        for stage_name, rule_name, lines in CADENCE:
            stage = Stage.objects.filter(name=stage_name).first()
            if stage is None:
                self.stdout.write(self.style.WARNING(
                    f'  stage "{stage_name}" not found — skipped'))
                continue

            defaults = {
                'stage': stage,
                'is_active': not options['disable'],
                'move_to_if_not_replied': lost_stage,
                'lost_reason': lost_reason,
                'not_replied_is_lost': True,
                'grace_after_last_step': timedelta(days=GRACE_DAYS),
            }
            rule, created = FollowupRule.objects.update_or_create(name=rule_name, defaults=defaults)
            # The channel flags are injected by each channel module's extension
            # and may not exist on a tenant without that module. Set what is
            # there; never crash on what is not.
            for flag in ('apply_whatsapp', 'apply_messenger', 'apply_instagram', 'apply_webbot'):
                if hasattr(rule, flag):
                    setattr(rule, flag, True)
            rule.save()

            rule.message_lines.all().delete()
            for index, (days, text) in enumerate(lines, 1):
                FollowupRuleMessage.objects.create(
                    rule=rule, sequence=index, duration=timedelta(days=days), body=text)
            made += created
            updated += (not created)

        self.stdout.write(self.style.SUCCESS(
            f'follow-up rules: {made} created, {updated} updated · lost stage "{lost_stage}" '
            f'· reason "{lost_reason}" · grace {GRACE_DAYS} d'))
        if options['disable']:
            self.stdout.write(self.style.WARNING('Rules are OFF.'))
        else:
            self.stdout.write('scan_followup_executions (core beat, every 2 h) will pick them up. '
                              'Sends respect the WhatsApp window and quiet hours.')
