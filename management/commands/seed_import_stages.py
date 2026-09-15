# -*- coding: utf-8 -*-
"""
Seed the client's shipping stages.

The list is theirs, confirmed on 2026-09-14: their original eleven, plus the
purchase stage they left blank (3), the import-approval / ACID wait as its own
stage, and delivery and licensing at the end.

The Arabic message texts below are **drafts**. They must be approved by Mr Khaled
or the General Manager and submitted to WhatsApp before any of them reaches a
customer — which is why `notify_customer` is seeded off for stages whose wording
is not signed off yet, and cancellation never sends automatically.

Re-running the command is safe: it updates by `code` and never duplicates.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

STAGES = [
    {
        'code': 'contract_reserved', 'sequence': 10,
        'name_ar': 'التعاقد والحجز', 'name_en': 'Contract and reservation',
        'fallback_text_ar': 'أهلاً {customer_name} 👋 تم التعاقد وحجز {model} {model_year} باسم حضرتك. '
                            'هنبدأ إجراءات الشراء ونطمّن حضرتك خطوة بخطوة.',
    },
    {
        'code': 'signed_and_paid', 'sequence': 20,
        'name_ar': 'توقيع العقد وتحويل الفلوس', 'name_en': 'Contract signed and funds transferred',
        'fallback_text_ar': 'تمام يا {customer_name} ✅ استلمنا العقد موقّع وتحويل حضرتك. '
                            'دلوقتي بنكمّل شراء العربية من المورد في ألمانيا.',
    },
    {
        'code': 'purchased', 'sequence': 30,
        'name_ar': 'شراء السيارة والتعاقد مع المورد', 'name_en': 'Car purchased from the supplier',
        'fallback_text_ar': 'مبروك يا {customer_name} 🎉 تم شراء {model} {model_year} رسمياً من المورد. '
                            'الخطوة الجاية استلامها وفحصها.',
    },
    {
        'code': 'received_inspected', 'sequence': 40,
        'name_ar': 'الاستلام والفحص', 'name_en': 'Received and inspected',
        'fallback_text_ar': 'استلمنا العربية وعملنا الفحص الكامل، وكل حاجة تمام. '
                            'دلوقتي بنجهّزها للنقل الداخلي.',
    },
    {
        'code': 'internal_transport', 'sequence': 50,
        'name_ar': 'النقل الداخلي', 'name_en': 'Internal transport',
        'fallback_text_ar': 'العربية في طريقها من المورد لمعرضنا في برلين.',
    },
    {
        'code': 'at_berlin', 'sequence': 60,
        'name_ar': 'وصول السيارة أرض المعرض ببرلين', 'name_en': 'Arrived at the Berlin showroom',
        'fallback_text_ar': 'العربية وصلت معرضنا في برلين 🚗 وهنبعت لحضرتك صور وفيديو من برا وجوا.',
        'attach_media': True,
    },
    {
        'code': 'prep_for_shipping', 'sequence': 70,
        'name_ar': 'تجهيز العربية للشحن الدولي', 'name_en': 'Prepared for international shipping',
        'fallback_text_ar': 'بنجهّز العربية للشحن الدولي: الأوراق والتأمين وحجز الشحنة.',
    },
    {
        'code': 'awaiting_acid', 'sequence': 80,
        'name_ar': 'انتظار الموافقة الاستيرادية ورقم ACID', 'name_en': 'Waiting for the import approval / ACID',
        'fallback_text_ar': 'العربية جاهزة، ومستنيين الموافقة الاستيرادية ورقم الـ ACID. '
                            'دي أطول خطوة وبتاخد وقت مش في إيدينا، وأول ما تخرج هنبلّغ حضرتك فوراً.',
    },
    {
        'code': 'shipped_bl', 'sequence': 90,
        'name_ar': 'الشحن الدولي وإصدار بوليصة الشحن', 'name_en': 'Shipped, bill of lading issued',
        'fallback_text_ar': 'العربية اتشحنت 🚢 على الباخرة {vessel}، وبوليصة الشحن رقم {bl_number}. '
                            'الوصول المتوقع {eta} على ميناء {port}. لينك التتبع: {tracking_url}',
    },
    {
        'code': 'at_egypt_port', 'sequence': 100,
        'name_ar': 'وصول السيارة الميناء في مصر', 'name_en': 'Arrived at the Egyptian port',
        'fallback_text_ar': 'العربية وصلت ميناء {port} 🇪🇬 وبدأنا إجراءات الإفراج الجمركي.',
    },
    {
        'code': 'customs_release', 'sequence': 110,
        'name_ar': 'الإفراج الجمركي', 'name_en': 'Customs release',
        'fallback_text_ar': 'إجراءات الإفراج الجمركي شغالة دلوقتي، وبنبلّغ حضرتك أول ما تخلص.',
    },
    {
        'code': 'out_of_port', 'sequence': 120,
        'name_ar': 'خروج السيارة من الميناء وفي الطريق للعميل', 'name_en': 'Out of the port, on the way',
        'fallback_text_ar': 'ألف مبروك يا {customer_name} 🎊 العربية خرجت من الميناء وفي طريقها لحضرتك.',
    },
    {
        'code': 'delivered', 'sequence': 130,
        'name_ar': 'التسليم ومحضر الاستلام', 'name_en': 'Delivered',
        'fallback_text_ar': 'تم التسليم ومحضر الاستلام ✅ ألف مبروك، ومستعدين لأي خدمة بعد الاستلام.',
    },
    {
        'code': 'licensing', 'sequence': 140, 'is_final': True,
        'name_ar': 'الترخيص', 'name_en': 'Licensing',
        'fallback_text_ar': 'الترخيص ممكن يبدأ بعد أسبوعين من خروج العربية من الميناء. '
                            'لو حابب نعمله لحضرتك، خدمة المندوب 3,000 جنيه وتكلفة الرخصة بتتحدد في مكتب الترخيص.',
    },
]


class Command(BaseCommand):
    help = "Create or update the client's 13 shipping stages and their draft messages"

    def add_arguments(self, parser):
        parser.add_argument('--enable-messages', action='store_true',
                            help="Switch the customer messages on. Only after the owner has approved "
                                 "the wording and WhatsApp has approved the templates.")

    @transaction.atomic
    def handle(self, *args, **options):
        from car_import.models import ImportStage

        enable = options['enable_messages']
        created = updated = 0

        for data in STAGES:
            defaults = {
                'name_ar': data['name_ar'],
                'name_en': data['name_en'],
                'sequence': data['sequence'],
                'fallback_text_ar': data.get('fallback_text_ar', ''),
                'fallback_text_en': data.get('fallback_text_en', ''),
                'attach_media': data.get('attach_media', False),
                'is_final': data.get('is_final', False),
                'notify_customer': enable,
            }
            _, was_created = ImportStage.objects.update_or_create(code=data['code'], defaults=defaults)
            created += was_created
            updated += (not was_created)

        self.stdout.write(self.style.SUCCESS(
            f"car_import: {created} stage(s) created, {updated} updated."
        ))
        if enable:
            self.stdout.write(self.style.WARNING(
                "Customer messages are ON. Make sure the owner approved this wording "
                "and WhatsApp approved the templates."
            ))
        else:
            self.stdout.write(
                "Customer messages are OFF — the drafts are in place and nothing will be sent. "
                "Re-run with --enable-messages once the owner signs off."
            )
