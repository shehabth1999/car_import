# -*- coding: utf-8 -*-
"""Who does the selling: the assistant, with people watching — or people.

The client's decision of 2026-09-20, in their own words, and it replaces the
one of 2026-09-16 that sent every money question to a colleague:

    1. الـ AI يعمل عرض سعر وفاتورة مبدئية، والمحاسب يأكد بس إن الفلوس وصلت،
       وفي الحالة دي يطلع عقد ويتبعت تلقائي.
    2. يتعامل في كل شيء متاح والموظف يراقبه فقط.

So the assistant prices the car, sends the quotation and the proforma invoice,
reads the customer's transfer screenshot and prepares the payment for one
click by the accountant. A person confirms that money arrived — nothing else
in the sale waits on a person.

It is a switch and not a rewrite, for the usual reason: the day management
wants the old behaviour back for a week, that is one row in
الإعدادات ← مفاتيح التشغيل, not a deployment.

What did NOT move, because the client's own approval matrix applies to staff
as much as to the assistant: a discount on the company's fees is management's
to give, and "the money arrived" is the accountant's to say.
"""

AI_FIRST_KEY = 'car_import.ai_handles_sales'
SIMULATED_QUOTES_KEY = 'car_import.ai_may_quote_simulated_cars'

_ON = ('1', 'true', 'yes', 'on')
_OFF = ('0', 'false', 'no', 'off')


def _value(key):
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=key).values('value').first()
    except Exception:
        return None
    return None if not row else str(row['value']).strip().lower()


def ai_first():
    """True unless somebody switched it off. The client's instruction is the
    default; a missing row must not quietly mean the old policy."""
    return _value(AI_FIRST_KEY) not in _OFF


def may_quote_simulated_cars():
    """A simulated advert is a fake car. Quotable only where somebody said so
    on purpose — the test tenant, while mobile.de access is pending."""
    return _value(SIMULATED_QUOTES_KEY) in _ON
