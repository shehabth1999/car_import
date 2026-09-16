# -*- coding: utf-8 -*-
"""Annex 2 — the vehicle specification the contract points at.

Clause 5.2 of the client's own contract makes this annex load-bearing: if an
option is missing on arrival, the customer is refunded *"وفقاً للأسعار الرسمية
المحددة في ملحق التوصيف (Configuration)"* — according to the prices in this
annex. So it is not a summary of the car; it is the list the money is settled
against, and anything left off it is a claim nobody can price later.

That shapes what goes on the page. Every line the contract can be argued over —
the configuration number, the VIN, the six options that set the deposit tier,
the exact trim and colour — appears whether it is filled in or not, with a
visible dash where the answer is missing. A silently omitted row reads as
"this car does not have that"; a dash reads as "nobody wrote it down", which is
the truth and is actionable.
"""
from django.utils.html import escape
from django.utils.translation import gettext as _


def as_html(contract, vehicle):
    deal = contract.deal
    rows = _rows(vehicle)
    options = _options(vehicle)

    body = ''.join(
        f'<tr><td>{escape(label)}</td><td class="v">{_value(value)}</td></tr>'
        for label, value in rows)
    option_rows = ''.join(
        f'<tr><td>{escape(label)}</td>'
        f'<td class="v">{"✔" if present else "—"}</td></tr>'
        for label, present in options)

    customer = escape(contract.customer_name or getattr(deal.partner, 'name', '') or '—')
    reference = escape(deal.name or '—')

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_('ملحق 2 — مواصفات السيارة')} · {reference}</title>
<style>
 body {{ font-family:'Cairo','Segoe UI',sans-serif; margin:2.5rem; color:#16324f;
        line-height:1.7; }}
 h1 {{ font-size:1.35rem; margin:0 0 .25rem; }}
 h2 {{ font-size:1.05rem; margin:2rem 0 .5rem; }}
 .meta {{ color:#55708c; font-size:.9rem; margin-bottom:1.5rem; }}
 table {{ width:100%; border-collapse:collapse; }}
 td {{ padding:.45rem .25rem; border-bottom:1px solid #e3eaf2; }}
 td.v {{ text-align:left; direction:ltr; width:45%; }}
 .missing {{ color:#b4530a; }}
 .note {{ color:#55708c; font-size:.85rem; margin-top:2rem;
          border-top:1px solid #e3eaf2; padding-top:1rem; }}
 bdi {{ unicode-bidi:isolate; }}
 @media print {{ body {{ margin:1.2cm; }} }}
</style></head><body>
<h1>ملحق رقم 2 — مواصفات السيارة</h1>
<div class="meta">
  العميل: <bdi>{customer}</bdi> &nbsp;·&nbsp; الصفقة: <bdi>{reference}</bdi>
  &nbsp;·&nbsp; التاريخ: <bdi>{contract.contract_date:%Y-%m-%d}</bdi>
</div>
<table>{body}</table>
<h2>المواصفات اللي بتحدد فئة الوديعة</h2>
<table>{option_rows}</table>
<p class="note">
هذا الملحق جزء لا يتجزأ من العقد. طبقاً للبند 5/2، أي اختلاف في الكماليات
غير الجوهرية يُعالج باسترداد نقدي وفقاً للأسعار الموضحة في هذا الملحق.
أي خانة مكتوب فيها «—» معناها إن البيان ده لسه مش متسجّل، ولازم يتكتب قبل
التوقيع.
</p>
</body></html>"""


def _rows(vehicle):
    return [
        ('الماركة', vehicle.make),
        ('الموديل', vehicle.model),
        ('الفئة (Trim)', vehicle.trim),
        ('سنة الموديل', vehicle.model_year),
        ('شهر الإنتاج', vehicle.production_month),
        ('رقم الكونفيجريشن', vehicle.configuration_number),
        ('رقم الشاسيه (VIN)', vehicle.vin),
        ('نوع الهيكل', vehicle.get_body_display() if vehicle.body else ''),
        ('اللون الخارجي', vehicle.colour_exterior),
        ('اللون الداخلي', vehicle.colour_interior),
        ('الفرش', vehicle.upholstery),
        ('سعة المحرك (cc)', vehicle.cc),
        ('القوة (حصان)', vehicle.hp),
        ('الوقود', vehicle.fuel),
        ('ناقل الحركة', vehicle.gearbox),
        ('معيار EURO', vehicle.euro_norm),
        ('بلد الصنع', vehicle.country_built),
        ('مصنّعة لسوق', vehicle.built_for_market),
        ('ميناء التصدير', vehicle.export_port),
        ('العداد (كم)', vehicle.mileage_km),
        ('الحالة', vehicle.get_condition_display() if vehicle.condition else ''),
        ('فابريكة من الخارج', 'نعم' if vehicle.accident_free else ''),
    ]


def _options(vehicle):
    from car_import.models.vehicle import TIER_OPTION_FIELDS

    labels = {
        'has_sunroof': 'فتحة سقف',
        'has_panorama': 'سقف بانوراما',
        'has_electric_trunk': 'شنطة كهربا',
        'has_electric_seats': 'كراسي كهربا',
        'has_leather_seats': 'كراسي جلد',
        'has_digital_cluster': 'عداد ديجيتال',
    }
    rows = [(labels[f], getattr(vehicle, f, False)) for f in TIER_OPTION_FIELDS]
    tier = 'كاملة' if vehicle.deposit_tier == 'full' else 'متوسطة'
    rows.append((f'الفئة الناتجة ({vehicle.tier_option_count} من 6)', tier))
    return rows


def _value(value):
    if value is None or value == '':
        return '<span class="missing">—</span>'
    if value is True:
        return '✔'
    return escape(str(value))
