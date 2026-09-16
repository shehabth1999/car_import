# -*- coding: utf-8 -*-
"""The price stack — the client's calculator, with the flexibility they asked for.

Reproduces `New Quotation.xlsx` exactly, then adds the three things the owner
said in the same message and the sheet does not do:

* **the port fee depends on which port.** The sheet's note says "about 50,000
  EGP"; the owner says Alexandria is 55,000 and Port Said is 105,000. Twice the
  money, and the sheet cannot tell them apart;
* **collecting from the showroom costs 5,000 EGP** more;
* **a customer may pay more than the deposit, or everything.** The sheet
  computes one number; real customers hand over what they feel like.

The Egyptian pounds and the euros are kept apart on purpose and never added
together. The EUR total is what the company is owed abroad; the EGP fees are
collected here, at arrival, and every EGP figure carries the rate it was
converted at and the note that it is indicative. Adding them into one headline
number is how a quote becomes a promise about an exchange rate nobody made.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

TWO = Decimal('0.01')
DEFAULT_VAT_RATE = Decimal('19')

#: Fee codes this engine expects in FeeSchedule. Seeded by seed_reference_data.
SHIPPING_FEE = 'shipping_cost'
EUR1_FEE = 'eur1_certificate'
RORO_FEE = 'shipping_vip_roro'
CONTAINER_FEE = 'shipping_container'
PORT_FEES = {'alexandria': 'port_alexandria', 'port_said': 'port_said'}
SHOWROOM_FEE = 'showroom_collection'


class PricingError(Exception):
    """A quote that cannot be produced honestly."""


def _money(value):
    return Decimal(value or 0).quantize(TWO, rounding=ROUND_HALF_UP)


def _pct(value):
    """19, not 19.00 — a Decimal keeps its trailing zeros and `:g` keeps them
    too, so a customer reads "VAT 19.00%" on an offer no human would write."""
    return f'{float(value):g}'


def _fee(code, default=None):
    """One fee amount from the table, or the default when it is not there."""
    try:
        from car_import.models import FeeSchedule
        row = FeeSchedule.in_force(code=code).first()
    except Exception:
        row = None
    if row is None or row.amount is None:
        return None if default is None else Decimal(default)
    return Decimal(row.amount)


def quote(gross_price_eur, *, eur1=False, shipping_type=None, port='alexandria',
          collect_from_showroom=False, admin_fee_discount_eur=0, vat_rate=None,
          fx_rate_egp=None, on=None):
    """The full stack for one car.

    Returns every line, not a total: an agent who cannot see where a number came
    from cannot defend it to a customer, and the client's own complaint about
    their current process is that nobody can reconstruct a price afterwards.
    """
    from car_import.models import PricingBand

    gross = Decimal(gross_price_eur or 0)
    if gross <= 0:
        raise PricingError('A car price is needed before anything can be calculated.')

    rate = Decimal(vat_rate if vat_rate is not None else DEFAULT_VAT_RATE)
    net = (gross / (Decimal(1) + rate / Decimal(100))).quantize(TWO, rounding=ROUND_HALF_UP)
    vat = _money(gross - net)

    band = PricingBand.for_gross(gross, on=on)
    if band is None:
        # The workbook's own behaviour: refuse rather than guess. Its bands have
        # gaps at the boundaries (…30000 then 30001…), so a price of 30,000.50
        # genuinely falls through, and that is worth saying out loud instead of
        # rounding it into a band nobody chose.
        raise PricingError(
            f'No pricing band covers {gross:,.2f} €. Check the bands in '
            f'Configuration → Pricing bands — the boundaries may have a gap.')

    shipping = _fee(SHIPPING_FEE, 4750)
    admin_before_discount = band.admin_fee_for(net)
    admin = admin_before_discount
    discount = Decimal(admin_fee_discount_eur or 0)
    if discount:
        # The owner asked for this: "ممكن يبقى في خصم على المصاريف الادارية".
        # It never turns a fee into a bigger discount than the fee itself.
        discount = min(discount, max(admin, Decimal(0)))
        admin = admin - discount

    eur1_fee = _fee(EUR1_FEE, 550) if eur1 else Decimal(0)

    shipping_extra = Decimal(0)
    if shipping_type == 'vip_roro':
        shipping_extra = _fee(RORO_FEE, 250)
    elif shipping_type == 'container':
        shipping_extra = _fee(CONTAINER_FEE, 1000)

    total_eur = _money(net + shipping + admin + eur1_fee + shipping_extra)
    deposit_pct = Decimal(band.deposit_pct)
    deposit_eur = _money(total_eur * deposit_pct / Decimal(100))

    # ── the Egyptian side, kept separate ────────────────────────────────────
    port_key = (port or 'alexandria').lower().replace(' ', '_')
    port_fee_code = PORT_FEES.get(port_key)
    port_fee_egp = _fee(port_fee_code, 55000 if port_key == 'alexandria' else 105000) \
        if port_fee_code else None
    showroom_egp = _fee(SHOWROOM_FEE, 5000) if collect_from_showroom else Decimal(0)
    egp_total = _money((port_fee_egp or Decimal(0)) + showroom_egp)

    lines = [
        {'code': 'gross', 'label_ar': 'إجمالي سعر العربية شامل الضريبة',
         'amount': _money(gross), 'currency': 'EUR'},
        {'code': 'vat', 'label_ar': f'الضريبة {_pct(rate)}% (بتسترد بعد التصدير)',
         'amount': -vat, 'currency': 'EUR'},
        {'code': 'net', 'label_ar': 'صافي سعر العربية', 'amount': net, 'currency': 'EUR'},
        {'code': 'shipping', 'label_ar': 'مصاريف الشحن', 'amount': _money(shipping),
         'currency': 'EUR'},
        # The fee BEFORE any discount. The discount is its own line below, so
        # the lines add up to the total; showing the reduced fee and the
        # discount together subtracts it twice on the page and leaves a quote
        # whose own rows disagree with its own bottom line.
        {'code': 'admin', 'label_ar': 'مصاريف إدارية', 'amount': _money(admin_before_discount),
         'currency': 'EUR'},
    ]
    if discount:
        lines.append({'code': 'admin_discount', 'label_ar': 'خصم على المصاريف الإدارية',
                      'amount': -_money(discount), 'currency': 'EUR'})
    if eur1:
        lines.append({'code': 'eur1', 'label_ar': 'شهادة يورو 1',
                      'amount': _money(eur1_fee), 'currency': 'EUR'})
    if shipping_extra:
        label = 'شحن VIP RORO' if shipping_type == 'vip_roro' else 'شحن بالحاوية'
        lines.append({'code': 'shipping_type', 'label_ar': label,
                      'amount': _money(shipping_extra), 'currency': 'EUR'})

    egp_lines = []
    if port_fee_egp is not None:
        port_label = 'ميناء الإسكندرية' if port_key == 'alexandria' else 'ميناء بورسعيد'
        egp_lines.append({'code': 'port', 'label_ar': f'مصاريف {port_label}',
                          'amount': _money(port_fee_egp), 'currency': 'EGP'})
    if showroom_egp:
        egp_lines.append({'code': 'showroom', 'label_ar': 'الاستلام من المعرض',
                          'amount': _money(showroom_egp), 'currency': 'EGP'})

    result = {
        'band': str(band),
        'band_id': band.pk,
        'vat_rate_pct': float(rate),
        'lines_eur': lines,
        'lines_egp': egp_lines,
        'net_eur': net,
        'vat_reclaimable_eur': vat,
        'total_eur': total_eur,
        'deposit_pct': float(deposit_pct),
        'deposit_eur': deposit_eur,
        'balance_eur': _money(total_eur - deposit_eur),
        'egp_due_on_arrival': egp_total,
        'port': port_key,
        'admin_fee_eur': _money(admin),
        'admin_fee_before_discount_eur': _money(admin_before_discount),
        'admin_fee_discount_eur': _money(discount),
        'notes_ar': [
            'السيارة فابريكة من الداخل والخارج.',
            'التحويل لحساب الشركة من الخارج، والدفع تحويل بنكي.',
            'الأسعار باليورو مش شاملة مصاريف الميناء في مصر — دي بتتحصّل عند الوصول.',
        ],
    }

    if fx_rate_egp:
        # Indicative only, and it says so. The company does not promise a rate.
        fx = Decimal(fx_rate_egp)
        result['fx_rate_egp'] = float(fx)
        result['total_egp_indicative'] = _money(total_eur * fx)
        result['notes_ar'].append(
            f'أي رقم بالجنيه تقريبي بسعر اليوم ({fx:,.2f}) وعليه عمولة تحويل 1.5–2%.')
    return result


def payment_plan(quote_result, paid_eur=None):
    """What is still owed once the customer has paid whatever they actually paid.

    The owner's point: *"ساعات العميل بيجي يدفع فلوس أكثر من المطلوب منه كـ
    deposit وممكن يدفع كل ثمن العربية"*. So this takes a real amount rather than
    assuming the deposit, and answers three questions an agent gets asked: is the
    deposit covered, what is left, and did they overpay.
    """
    total = Decimal(quote_result['total_eur'])
    deposit = Decimal(quote_result['deposit_eur'])
    paid = Decimal(paid_eur) if paid_eur is not None else deposit

    return {
        'total_eur': _money(total),
        'deposit_required_eur': _money(deposit),
        'paid_eur': _money(paid),
        'deposit_covered': paid >= deposit,
        'remaining_eur': _money(max(total - paid, Decimal(0))),
        'fully_paid': paid >= total,
        # Overpayment is a fact worth surfacing, not an error: the company holds
        # it against the balance, and an agent who cannot see it will ask the
        # customer for money they already sent.
        'overpaid_eur': _money(max(paid - total, Decimal(0))),
    }
