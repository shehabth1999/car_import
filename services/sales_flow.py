# -*- coding: utf-8 -*-
"""The sale, end to end, as the assistant runs it (`services/policy.py`).

    price → quotation → customer says yes → deal + proforma invoice →
    customer sends the transfer screenshot → payment receipt (pending) →
    ACCOUNTANT ACCEPTS → money credited, customer told, contract issued and sent

Everything here is called from two places: the assistant's tools
(`tools/sales_tools.py`) and the accountant's one button
(`PaymentReceipt.action_accept`). Nothing in it decides policy — it does what
it is asked, writes a note in the thread so the people watching can see it
happened, and returns plain dicts the callers turn into words.

Rows are created from a Celery worker, where there is no request and so no
`env.branch`: the branch is taken from the deal, else the company's first.
"""
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

ACCOUNTING_GROUPS = ['car_import.accountant', 'car_import.management']
BANK_DETAILS_KEY = 'car_import.bank_details_text'
PROFORMA_VALID_DAYS = 3


# ── small helpers ────────────────────────────────────────────────────────────
def to_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value).replace(',', '').replace(' ', ''))
    except (InvalidOperation, ValueError):
        return None


def default_branch(deal=None):
    if deal is not None and getattr(deal, 'branch_id', None):
        return deal.branch
    from modules.base.models import Branch
    manager = getattr(Branch, 'all_objects', Branch.objects)
    return manager.order_by('id').first()


def absolute_url(url):
    if not url or str(url).startswith(('http://', 'https://')):
        return url
    base = str(getattr(settings, 'BASE_URL', '') or '').rstrip('/')
    return f'{base}{url}' if base else url


def accountants():
    from car_import.tasks import _users_in_groups
    return _users_in_groups(ACCOUNTING_GROUPS)


def may_confirm_money(user):
    """Management and the accountant. An agent never confirms their own
    customer's money — that is the one control this flow keeps."""
    if user is None:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return any(u.pk == user.pk for u in accountants())


def owners(partner):
    from car_import.tasks import _owner_users_for_partner
    return _owner_users_for_partner(partner) or []


def conversation_of(partner, conversation=None):
    if conversation is not None:
        return conversation
    from car_import.services.chat_actions import latest_conversation_for
    return latest_conversation_for(partner) if partner is not None else None


def note(partner, body, recipients=(), conversation=None, subject='', url=''):
    """What happened, in the thread, for the people watching. Best effort."""
    try:
        from car_import.services import internal_note
        target = conversation_of(partner, conversation)
        if target is None:
            return False
        return internal_note.post(target, body, recipients=list(recipients),
                                  subject=subject, url=url)
    except Exception:
        logger.exception('car_import: could not post the sales note')
        return False


def form_url(menu_key, model, pk):
    try:
        from modules.base.models.menu_item import MenuItem
        menu = MenuItem.objects.filter(key=menu_key).values_list('id', flat=True).first()
    except Exception:
        menu = None
    if not menu:
        return ''
    return f'/genie/{menu}/?model={model}&module=car_import&view_type=form&id={pk}'


def send_text(partner, text):
    from car_import.services import stage_notifier
    if not stage_notifier.messages_enabled():
        return {'sent': False, 'error': 'customer messages are switched off'}
    if stage_notifier.customer_opted_out(partner):
        return {'sent': False, 'error': 'the customer asked not to be messaged'}
    try:
        result = stage_notifier._send_free_text(partner, text) or {}
    except Exception as exc:  # noqa: BLE001
        logger.exception('car_import: could not message the customer')
        return {'sent': False, 'error': str(exc)}
    if result.get('success') is False or result.get('status') is False:
        return {'sent': False, 'error': result.get('error') or result.get('message') or 'send failed'}
    return {'sent': True}


def send_document(partner, file_field, caption):
    from car_import.services import stage_notifier
    if not stage_notifier.messages_enabled():
        return {'sent': False, 'error': 'customer messages are switched off'}
    if stage_notifier.customer_opted_out(partner):
        return {'sent': False, 'error': 'the customer asked not to be messaged'}
    try:
        from modules.chat.services.omnichannel_send_service import OmnichannelSendService
        result = OmnichannelSendService().send_and_broadcast(
            partner, {'url': absolute_url(file_field.url)}, message_type='document',
            filename=file_field.name.rsplit('/', 1)[-1], caption=caption) or {}
    except Exception as exc:  # noqa: BLE001
        logger.exception('car_import: could not send the document')
        return {'sent': False, 'error': str(exc)}
    if result.get('success') is False or result.get('status') is False:
        return {'sent': False, 'error': result.get('error') or 'send failed'}
    return {'sent': True}


def bank_details_text():
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=BANK_DETAILS_KEY).values('value').first()
    except Exception:
        return ''
    return str((row or {}).get('value') or '').strip()


# ── the car ──────────────────────────────────────────────────────────────────
def find_listing(reference):
    """The stored advert behind a reference the search tool returned."""
    from car_import.models import SupplierListing
    ref = str(reference or '').strip()
    if not ref:
        return None
    return SupplierListing.objects.filter(ad_id=ref).order_by('-id').first()


def listing_label(listing):
    bits = [listing.make, listing.model, listing.version]
    label = ' '.join(str(b) for b in bits if b).strip()
    if listing.model_year:
        label += f' — {listing.model_year}'
    return label[:190]


def vehicle_from_listing(listing):
    """The deal's car, created once from the advert it was quoted from."""
    from car_import.models import Vehicle
    if listing is None:
        return None
    if listing.vehicle_id:
        return listing.vehicle
    mileage = listing.mileage_km or 0
    vehicle = Vehicle(
        make=listing.make or '—', model=listing.model or '—',
        trim=(listing.version or '')[:128], model_year=listing.model_year,
        cc=listing.cc, hp=listing.power_hp, fuel=listing.fuel or '', gearbox=listing.gearbox or '',
        colour_exterior=listing.colour_exterior or '', mileage_km=listing.mileage_km,
        condition='zero' if (listing.condition_new or mileage < 50) else 'used',
        accident_free=bool(listing.accident_free), listing_url=listing.url or '',
        dealer_name=(listing.seller_name or '')[:128], vatable=bool(listing.vatable),
        price_gross_eur=listing.price_gross_eur,
        notes=f'اتعملت من إعلان {listing.ad_id} اللي المساعد سعّره.')
    vehicle.save()
    type(listing)._base_manager.filter(pk=listing.pk).update(vehicle=vehicle)
    listing.vehicle = vehicle
    return vehicle


# ── price and quotation ──────────────────────────────────────────────────────
PRICE_OPTIONS = ('with_eur1', 'shipping_type', 'port', 'collect_from_showroom')


def price(gross_price_eur, with_eur1=False, shipping_type='', port='alexandria',
          collect_from_showroom=False):
    """The calculator's answer, nothing written. Raises PricingError."""
    from car_import.services import pricing
    return pricing.quote(gross_price_eur, eur1=bool(with_eur1),
                         shipping_type=shipping_type or None, port=port or 'alexandria',
                         collect_from_showroom=bool(collect_from_showroom))


def make_quote(partner, gross_price_eur, car_label='', listing=None, conversation=None,
               with_eur1=False, shipping_type='', port='alexandria',
               collect_from_showroom=False, admin_fee_discount_eur=None, price_source=''):
    """A quotation, frozen and marked sent. Raises ValidationError (an
    unapproved discount, no price) — the caller says why."""
    from car_import.models import Quote
    from car_import.services.chat_actions import open_deal_for

    deal = open_deal_for(partner)
    quote = Quote(
        partner=partner, deal=deal, branch=default_branch(deal),
        assigned_to=getattr(deal, 'assigned_to', None),
        vehicle=getattr(listing, 'vehicle', None) if listing is not None else None,
        car_label=(car_label or (listing_label(listing) if listing is not None else ''))[:190],
        listing=listing, issued_by_ai=True,
        gross_price_eur=gross_price_eur, with_eur1=bool(with_eur1),
        shipping_type=shipping_type or '', port=port or 'alexandria',
        collect_from_showroom=bool(collect_from_showroom),
        admin_fee_discount_eur=admin_fee_discount_eur or 0,
        valid_until=timezone.localdate() + timedelta(days=7),
        notes=price_source or '', state='sent', sent_at=timezone.now())
    quote.save()
    if quote.pricing_error or not quote.total_eur:
        raise ValidationError(quote.pricing_error or _("There is no price for this car."))
    return quote


def latest_open_quote(partner):
    from car_import.models import Quote
    return (Quote.all_objects.filter(partner=partner, state__in=['sent', 'accepted'])
            .exclude(total_eur=0).order_by('-id').first())


# ── the customer said yes ────────────────────────────────────────────────────
def ensure_deal(partner, quote=None):
    """The customer's open deal, or a new one opened for this sale."""
    from car_import.models import CarDeal
    from car_import.services.chat_actions import lead_for, open_deal_for

    deal = open_deal_for(partner)
    if deal is not None:
        return deal, False
    lead = lead_for(partner, create=True)
    program = getattr(lead, 'ka_program', None)
    if program not in dict(CarDeal.PROGRAM):
        program = 'personal'
    listing = getattr(quote, 'listing', None)
    vehicle = getattr(quote, 'vehicle', None) or vehicle_from_listing(listing)
    owner = next(iter(owners(partner)), None)
    deal = CarDeal(partner=partner, lead=lead, program=program, vehicle=vehicle,
                   branch=default_branch(), assigned_to=owner)
    deal.save()
    return deal, True


def accept_quote(quote, deal):
    quote.deal = deal
    quote.state = 'accepted'
    if quote.vehicle_id is None and deal.vehicle_id:
        quote.vehicle_id = deal.vehicle_id
    quote.save()
    changed = []
    for field, value in (('amount_agreed', quote.total_eur), ('currency_id', quote.currency_id),
                         ('accepted_quote_id', quote.pk)):
        if getattr(deal, field) != value:
            setattr(deal, field, value)
            changed.append(field)
    if changed:
        deal.save()
    return quote


def issue_proforma(quote, deal, by_ai=True):
    """One open proforma per quotation: asking twice for the same deposit is
    how a customer pays twice."""
    from car_import.models import ProformaInvoice
    from car_import.services import proforma_document

    existing = (ProformaInvoice.all_objects.filter(quote=quote)
                .exclude(state='cancelled').order_by('-id').first())
    if existing is not None:
        return existing, False

    invoice = ProformaInvoice(
        partner=quote.partner, deal=deal, quote=quote, branch=default_branch(deal),
        car_label=(quote.car_label or (str(quote.vehicle) if quote.vehicle_id else ''))[:190],
        currency=quote.currency, total_amount=quote.total_eur, deposit_pct=quote.deposit_pct,
        amount_due=quote.deposit_eur,
        valid_until=timezone.localdate() + timedelta(days=PROFORMA_VALID_DAYS),
        bank_details_text=bank_details_text(), issued_by_ai=bool(by_ai))
    invoice.save()
    proforma_document.attach(invoice)
    return invoice, True


def send_proforma(invoice):
    caption = f'فاتورة مبدئية {invoice.name} — المطلوب دلوقتي {invoice.amount_due:,.2f} €'
    if invoice.document:
        outcome = send_document(invoice.partner, invoice.document, caption)
    else:
        from car_import.services import proforma_document
        outcome = send_text(invoice.partner, proforma_document.as_text(invoice))
    if outcome.get('sent') and invoice.bank_details_text:
        send_text(invoice.partner,
                  'بيانات التحويل:\n' + invoice.bank_details_text
                  + f'\n\nبرجاء كتابة رقم الفاتورة {invoice.name} في بيان التحويل، '
                    'وابعتلنا صورة التحويل هنا.')
    if outcome.get('sent'):
        type(invoice)._base_manager.filter(pk=invoice.pk).update(sent_at=timezone.now())
    return outcome


# ── the screenshot ───────────────────────────────────────────────────────────
def record_receipt(partner, conversation, screenshot, amount=None, currency_code='EUR',
                   transfer_date=None, sender_name='', bank_name='', reference='',
                   confidence='', remarks=''):
    """A pending receipt, checked against what we asked for. Never credited here."""
    from car_import.models import PaymentReceipt, ProformaInvoice
    from car_import.services import currencies
    from car_import.services.chat_actions import open_deal_for

    deal = open_deal_for(partner)
    invoice = (ProformaInvoice.all_objects.filter(partner=partner)
               .exclude(state__in=['cancelled', 'paid']).order_by('-id').first())
    quote = getattr(invoice, 'quote', None) or getattr(deal, 'accepted_quote', None) \
        or latest_open_quote(partner)

    code = (currency_code or 'EUR').strip().upper()
    currency = currencies.by_code(code) or currencies.eur()
    amount = to_decimal(amount)
    checks = [remarks.strip()] if (remarks or '').strip() else []

    credited = amount if (amount is not None and code == 'EUR') else None
    if amount is None:
        checks.append('المبلغ مش واضح في الصورة — اكتبه من كشف الحساب.')
    elif code != 'EUR':
        checks.append(f'التحويل بعملة {code}: اكتب المعادل باليورو قبل القبول.')
    if invoice is not None and credited is not None:
        due = invoice.remaining_due
        if due and credited < due:
            checks.append(f'المبلغ ({credited:,.2f} €) أقل من المطلوب في {invoice.name} ({due:,.2f} €).')
        elif due and credited > due:
            checks.append(f'المبلغ ({credited:,.2f} €) أكتر من المطلوب في {invoice.name} ({due:,.2f} €).')
    if invoice is None:
        checks.append('مفيش فاتورة مبدئية مفتوحة للعميل — اتأكد التحويل ده على إيه.')
    if transfer_date and transfer_date > timezone.localdate():
        checks.append('تاريخ التحويل في المستقبل.')
    name = (sender_name or '').strip()
    if name and partner is not None and getattr(partner, 'name', ''):
        first = str(partner.name).split()[0]
        if first and first not in name:
            checks.append(f'اسم المحوِّل ({name}) مش اسم العميل ({partner.name}).')
    if reference:
        twin = (PaymentReceipt.all_objects.filter(bank_reference=reference.strip())
                .exclude(state='rejected').first())
        if twin is not None:
            checks.append(f'نفس رقم العملية موجود في {twin.name} — ممكن تكون نفس التحويلة.')

    receipt = PaymentReceipt(
        partner=partner, deal=deal, quote=quote, proforma=invoice, branch=default_branch(deal),
        conversation_ref=str(getattr(conversation, 'pk', '') or ''), source='ai',
        screenshot=screenshot, amount=amount, currency=currency, amount_credited=credited,
        transfer_date=transfer_date, sender_name=name[:190], bank_name=(bank_name or '')[:128],
        bank_reference=(reference or '').strip()[:128],
        ai_confidence=confidence if confidence in ('high', 'medium', 'low') else '',
        ai_remarks='\n'.join(checks))
    receipt.save()
    return receipt


def announce_receipt(receipt, conversation=None):
    """Tell the accountant, in the thread, with the link to the one button."""
    amount = (f'{receipt.amount:,.2f} {getattr(receipt.currency, "code", "")}'
              if receipt.amount is not None else 'مش واضح')
    lines = [f'💶 تحويل محتاج تأكيد — {receipt.name}',
             f'العميل: {getattr(receipt.partner, "name", "") or "—"}',
             f'المبلغ في الصورة: {amount}']
    if receipt.proforma_id:
        lines.append(f'الفاتورة المبدئية: {receipt.proforma.name} — المطلوب '
                     f'{receipt.proforma.remaining_due:,.2f} €')
    if receipt.transfer_date:
        lines.append(f'تاريخ التحويل: {receipt.transfer_date}')
    if receipt.sender_name:
        lines.append(f'المحوِّل: {receipt.sender_name}')
    if receipt.bank_reference:
        lines.append(f'رقم العملية: {receipt.bank_reference}')
    if receipt.ai_remarks:
        lines.append('راجع:\n' + receipt.ai_remarks)
    lines.append('افتح الإيصال واضغط «قبول — الفلوس وصلت». بعدها العميل بيتبلّغ والعقد بيطلع ويتبعت لوحده.')
    url = form_url('car_import_menu_receipts', 'car_import.paymentreceipt', receipt.pk)
    recipients = accountants() or owners(receipt.partner)
    return note(receipt.partner, '\n'.join(lines), recipients=recipients,
                conversation=conversation, subject=f'تحويل محتاج تأكيد — {receipt.name}', url=url)


# ── the one button ───────────────────────────────────────────────────────────
def accept_receipt(receipt, user=None):
    if receipt.state != 'pending':
        raise ValidationError(_("This receipt was already %(state)s.")
                              % {'state': receipt.get_state_display()})
    if user is not None and not may_confirm_money(user):
        raise ValidationError(_("Only the accountant or management confirms that money arrived."))
    credited = receipt.amount_credited
    if not credited or credited <= 0:
        raise ValidationError(_("Enter the amount to credit in EUR before accepting."))

    deal = receipt.deal
    quote = receipt.quote or getattr(receipt.proforma, 'quote', None) \
        or getattr(deal, 'accepted_quote', None)

    if quote is not None:
        if deal is not None and deal.accepted_quote_id != quote.pk:
            accept_quote(quote, deal)
        quote.paid_eur = (quote.paid_eur or Decimal(0)) + credited
        quote.save()                       # re-runs the plan and syncs the deal's marks
    elif deal is not None:
        deal.amount_paid_marked = (deal.amount_paid_marked or Decimal(0)) + credited
        deal.payment_state = 'partially_paid'
        deal.save()

    receipt.state = 'accepted'
    receipt.reviewed_by = user
    receipt.reviewed_at = timezone.now()
    receipt.save()
    if receipt.proforma_id:
        receipt.proforma.refresh_paid()

    deposit_covered = bool(getattr(quote, 'deposit_covered', False)) if quote is not None else True
    remaining = getattr(quote, 'remaining_eur', None)

    text = f'تم تأكيد استلام مبلغ {credited:,.2f} € ✅ — شكراً لحضرتك.'
    if remaining:
        text += f'\nالمتبقي من إجمالي العربية: {remaining:,.2f} €.'
    told = send_text(receipt.partner, text)

    contract = {'issued': False, 'sent': False, 'reason': 'مقدم التعاقد لسه متغطاش بالكامل'}
    if deal is not None and deposit_covered:
        contract = issue_and_send_contract(deal, user=user)
    elif deal is None:
        contract['reason'] = 'مفيش صفقة مفتوحة للعميل'

    summary = _contract_summary(contract)
    type(receipt)._base_manager.filter(pk=receipt.pk).update(contract_outcome=summary[:255])
    note(receipt.partner,
         f'✅ {getattr(user, "name", None) or "المحاسب"} أكّد استلام {credited:,.2f} € ({receipt.name}).\n'
         f'العميل اتبلّغ: {"أيوه" if told.get("sent") else "لأ — " + str(told.get("error"))}\n'
         f'العقد: {summary}',
         recipients=owners(receipt.partner), subject=f'تم تأكيد دفعة — {receipt.name}')
    if deal is not None:
        deal.message_post(body=f'تأكيد استلام {credited:,.2f} € ({receipt.name}). العقد: {summary}')
    return {'credited': credited, 'contract': contract, 'summary': summary}


def reject_receipt(receipt, user=None):
    receipt.state = 'rejected'
    receipt.reviewed_by = user
    receipt.reviewed_at = timezone.now()
    receipt.save()
    note(receipt.partner,
         f'⛔ {receipt.name} اترفض'
         + (f': {receipt.reject_reason}' if receipt.reject_reason else '')
         + '\nمفيش أي مبلغ اتسجّل. كمّل مع العميل من هنا.',
         recipients=owners(receipt.partner), subject=f'إيصال مرفوض — {receipt.name}')


def _contract_summary(outcome):
    if outcome.get('sent'):
        return 'اتعمل واتبعت للعميل'
    if outcome.get('issued'):
        return 'اتعمل ومتبعتش: ' + str(outcome.get('reason') or '')
    return 'متعملش: ' + str(outcome.get('reason') or '')


# ── the contract ─────────────────────────────────────────────────────────────
CONTRACT_DETAIL_LABELS = {
    'customer_name': 'الاسم زي البطاقة',
    'customer_national_id': 'الرقم القومي',
    'car_model': 'موديل العربية',
    'contract_total_eur': 'إجمالي العقد',
    'deposit_pct': 'نسبة مقدم التعاقد',
}


def draft_contract(deal):
    from car_import.models import Contract
    contract = (Contract.all_objects.filter(deal=deal).exclude(state='cancelled')
                .order_by('-id').first())
    if contract is None:
        contract = Contract(deal=deal, branch=default_branch(deal))
        contract.prefill_from_deal()
        _balance_contract(contract)
        contract.save()
    return contract


def missing_contract_fields(contract):
    values = contract.values()
    missing = []
    for token in contract.REQUIRED_TOKENS:
        value = str(values.get(token) or '').strip()
        if not value or value in ('0', '0.00'):
            missing.append(token)
    return missing


def save_contract_details(deal, full_name='', national_id='', address='', email=''):
    contract = draft_contract(deal)
    if contract.state in ('generated', 'signed'):
        return contract, []
    if full_name.strip():
        contract.customer_name = full_name.strip()[:190]
        if not contract.shipping_name or contract.shipping_name == getattr(deal.partner, 'name', ''):
            contract.shipping_name = contract.customer_name
    digits = ''.join(ch for ch in str(national_id or '') if ch.isdigit())
    if digits:
        if len(digits) != 14:
            raise ValidationError({'customer_national_id': _(
                "The national ID is 14 digits; this one has %(n)d.") % {'n': len(digits)}})
        contract.customer_national_id = digits
    if address.strip():
        contract.customer_address = address.strip()[:255]
    if email.strip():
        contract.customer_email = email.strip()
    contract.prefill_from_deal()
    _balance_contract(contract)
    contract.save()
    return contract, missing_contract_fields(contract)


def issue_and_send_contract(deal, user=None):
    """Fill the lawyer's template and send it. Refuses rather than sending a
    contract with a blank where the name or the price belongs."""
    try:
        contract = draft_contract(deal)
        if contract.state == 'signed':
            return {'issued': True, 'sent': bool(contract.sent_at), 'reason': 'العقد موقّع بالفعل'}
        if contract.state != 'generated':
            contract.prefill_from_deal()
            _balance_contract(contract)
            missing = missing_contract_fields(contract)
            if missing:
                contract.save()
                labels = '، '.join(CONTRACT_DETAIL_LABELS.get(m, m) for m in missing)
                send_text(deal.partner,
                          'عشان نطلّع العقد محتاجين من حضرتك: ' + labels + '.')
                return {'issued': False, 'sent': False, 'missing': missing,
                        'reason': 'ناقص: ' + labels}
            contract.save()
            contract.generate(user=user)
        if contract.sent_at:
            return {'issued': True, 'sent': True, 'reason': ''}
        outcome = send_document(deal.partner, contract.document,
                                'عقد الاستيراد — برجاء المراجعة والتوقيع')
        if not outcome.get('sent'):
            return {'issued': True, 'sent': False, 'reason': outcome.get('error') or 'send failed'}
        contract.sent_at = timezone.now()
        contract.save()
        contract.message_post(body='العقد اتبعت للعميل تلقائياً بعد تأكيد الدفعة.')
        return {'issued': True, 'sent': True, 'reason': ''}
    except Exception as exc:  # noqa: BLE001 — the accountant must still get their answer
        logger.exception('car_import: could not issue the contract for deal %s', deal.pk)
        reason = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        return {'issued': False, 'sent': False, 'reason': reason}


def _balance_contract(contract):
    """The contract refuses to save when its payment lines do not add up. What
    is not the down payment is, until somebody says otherwise, the transfer."""
    total = contract.total_eur or Decimal(0)
    down = contract.down_payment_eur or Decimal(0)
    rest = (contract.bank_transfer_eur or Decimal(0)) + (contract.cash_on_bl_eur or Decimal(0))
    if total and down + rest != total:
        contract.bank_transfer_eur = max(total - down - (contract.cash_on_bl_eur or Decimal(0)),
                                         Decimal(0))
