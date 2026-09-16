# -*- coding: utf-8 -*-
"""A price offer, frozen at the moment it was given.

The client's complaint about their current way of working was not that the
calculator is wrong — it is a perfectly good spreadsheet. It is that a price
quoted in March cannot be reconstructed in June: the sheet has moved on, the
salesman remembers a number, and nobody can say which fee schedule produced it.

So a quote stores its **results**, not only its inputs. Every figure the
customer was shown is written into the row, along with the band that produced
it. Re-reading a quote never re-runs the calculator, which means changing a
band tomorrow cannot silently rewrite what somebody was promised yesterday.
Pressing *Recalculate* re-runs it, deliberately, with a person's name on it.

The lines are stored too, for the same reason and one more: they are what gets
printed and sent, and a quote whose rows are regenerated from today's rules is
not the quote the customer is holding.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.base.decorators import action
from modules.base.models.base import BaseModel
from modules.base.models.managers import BranchAwareManager
from modules.base.models.mixins import BranchMixin, SequenceMixin
from modules.notifications.models.mixins import FullChatterMixin


class Quote(SequenceMixin, BaseModel, BranchMixin, FullChatterMixin):
    """One price offer for one car, for one customer."""

    sequence_code = 'car_import.quote'

    objects = BranchAwareManager()
    all_objects = models.Manager()

    _mail_track = {
        'state': None,
        'total_eur': None,
        'deposit_eur': None,
        'paid_eur': None,
    }

    STATE = [
        ('draft', _("Draft")),
        ('sent', _("Sent to the customer")),
        ('accepted', _("Accepted")),
        ('declined', _("Declined")),
        ('expired', _("Expired")),
    ]
    SHIPPING_TYPE = [
        ('', _("Standard")),
        ('vip_roro', _("VIP RORO")),
        ('container', _("Container")),
    ]
    PORT = [
        ('alexandria', _("Alexandria")),
        ('port_said', _("Port Said")),
    ]

    # ── identity ────────────────────────────────────────────────────────────
    name = models.CharField(max_length=32, blank=True, verbose_name=_("Reference"))
    state = models.CharField(max_length=16, choices=STATE, default='draft',
                             verbose_name=_("Status"))
    partner = models.ForeignKey('base.Partner', null=True, blank=True, on_delete=models.PROTECT,
                                related_name='car_quotes', verbose_name=_("Customer"))
    deal = models.ForeignKey('car_import.CarDeal', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='quotes',
                             verbose_name=_("Deal"))
    vehicle = models.ForeignKey('car_import.Vehicle', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='quotes',
                                verbose_name=_("Car"))
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='car_quotes',
                                    verbose_name=_("Sales agent"))
    quote_date = models.DateField(default=timezone.localdate, verbose_name=_("Date"))
    valid_until = models.DateField(null=True, blank=True, verbose_name=_("Valid until"))

    # ── what the salesman types ─────────────────────────────────────────────
    gross_price_eur = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name=_("Price with VAT (EUR)"),
        help_text=_("The number on the German advert — everything else follows from it"))
    with_eur1 = models.BooleanField(default=False, verbose_name=_("EUR 1 certificate"))
    shipping_type = models.CharField(max_length=16, choices=SHIPPING_TYPE, blank=True, default='',
                                     verbose_name=_("Shipping"))
    port = models.CharField(max_length=16, choices=PORT, default='alexandria',
                            verbose_name=_("Port of arrival"))
    collect_from_showroom = models.BooleanField(default=False,
                                                verbose_name=_("Collected from the showroom"))
    admin_fee_discount_eur = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name=_("Discount on the admin fee (EUR)"),
        help_text=_("Never more than the fee itself"))
    vat_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=19,
                                       verbose_name=_("VAT %"))
    fx_rate_egp = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, verbose_name=_("EGP per EUR"),
        help_text=_("Only to show the customer an indicative figure. The company does not "
                    "promise a rate"))

    # ── what the calculator answered, frozen ────────────────────────────────
    # Every field from here down is `editable=False`, which in this platform
    # means "render it, never write it from a payload"
    # (`genie_serializer/model_map.py:_is_read_only`). Two reasons, one of them
    # discovered the hard way:
    #
    # 1. the engine owns these numbers. A `readonly` flag in the view dict only
    #    greys the input — the form still posts the value back, and the write
    #    path would happily take it;
    # 2. posting them back is not harmless. The form sends a decimal as a JSON
    #    float, and Django's DecimalField turns a float into a Decimal through
    #    `Context(prec=max_digits).create_decimal_from_float`, which pads
    #    40336.97 out to 40336.9700000 — seven decimal places where the column
    #    allows two. The save then fails with "Enter a number with no more than
    #    2 decimal places" on a figure the user never touched. Whole-numbered
    #    floats survive, so it only breaks on the amounts that have cents,
    #    which is most of them.
    band = models.ForeignKey('car_import.PricingBand', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='quotes',
                             verbose_name=_("Band"), editable=False)
    band_label = models.CharField(max_length=120, blank=True, verbose_name=_("Band used"), editable=False)
    net_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                  verbose_name=_("Net price (EUR)"), editable=False)
    vat_reclaimable_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                              verbose_name=_("VAT reclaimed (EUR)"), editable=False)
    shipping_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name=_("Shipping (EUR)"), editable=False)
    admin_fee_before_discount_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                        verbose_name=_("Admin fee (EUR)"), editable=False)
    admin_fee_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name=_("Admin fee after discount (EUR)"), editable=False)
    eur1_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                   verbose_name=_("EUR 1 (EUR)"), editable=False)
    shipping_extra_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                             verbose_name=_("Shipping option (EUR)"), editable=False)
    total_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                    verbose_name=_("Total selling price (EUR)"), editable=False)
    deposit_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                      verbose_name=_("Deposit %"), editable=False)
    deposit_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                      verbose_name=_("Deposit (EUR)"), editable=False)
    balance_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                      verbose_name=_("Balance (EUR)"), editable=False)
    port_fee_egp = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name=_("Port fees (EGP)"), editable=False)
    showroom_fee_egp = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           verbose_name=_("Showroom collection (EGP)"), editable=False)
    egp_due_on_arrival = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                             verbose_name=_("Due on arrival (EGP)"), editable=False)
    total_egp_indicative = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                               verbose_name=_("Indicative total (EGP)"), editable=False)
    calculated_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Calculated at"), editable=False)
    pricing_error = models.CharField(max_length=255, blank=True, verbose_name=_("Why there is no price"), editable=False)

    # ── what the customer actually paid ─────────────────────────────────────
    # The owner's point, in their own words: "ساعات العميل بيجي يدفع فلوس أكثر
    # من المطلوب منه كـ deposit وممكن يدفع كل ثمن العربية". So this is a real
    # amount somebody types, not a status somebody picks.
    paid_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                   verbose_name=_("Paid so far (EUR)"))
    deposit_covered = models.BooleanField(default=False, verbose_name=_("Deposit covered"), editable=False)
    fully_paid = models.BooleanField(default=False, verbose_name=_("Paid in full"), editable=False)
    remaining_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name=_("Still owed (EUR)"), editable=False)
    overpaid_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name=_("Overpaid (EUR)"), editable=False)

    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Sent at"), editable=False)

    class Meta:
        verbose_name = _("Quotation")
        verbose_name_plural = _("Quotations")
        ordering = ['-id']
        indexes = [
            models.Index(fields=['state', 'quote_date']),
            models.Index(fields=['partner']),
        ]

    def __str__(self):
        return f"{self.name or '—'} · {self.total_eur:,.0f} €"

    # ── the calculation ─────────────────────────────────────────────────────
    def recalculate(self, save_lines=True):
        """Re-run the calculator and freeze the answer onto this row."""
        from car_import.services import pricing

        self.pricing_error = ''
        if not self.gross_price_eur:
            # Not an error worth shouting about: a salesman opens the form
            # before they have the price. Everything simply stays at zero.
            self._zero_results()
            return None

        try:
            result = pricing.quote(
                self.gross_price_eur,
                eur1=self.with_eur1,
                shipping_type=self.shipping_type or None,
                port=self.port,
                collect_from_showroom=self.collect_from_showroom,
                admin_fee_discount_eur=self.admin_fee_discount_eur,
                vat_rate=self.vat_rate_pct,
                fx_rate_egp=self.fx_rate_egp,
            )
        except pricing.PricingError as exc:
            self._zero_results()
            self.pricing_error = str(exc)
            return None

        self.band_id = result['band_id']
        self.band_label = result['band']
        self.net_eur = result['net_eur']
        self.vat_reclaimable_eur = result['vat_reclaimable_eur']
        self.total_eur = result['total_eur']
        self.deposit_pct = Decimal(str(result['deposit_pct']))
        self.deposit_eur = result['deposit_eur']
        self.balance_eur = result['balance_eur']
        self.admin_fee_eur = result['admin_fee_eur']
        self.admin_fee_before_discount_eur = result['admin_fee_before_discount_eur']
        self.egp_due_on_arrival = result['egp_due_on_arrival']
        self.total_egp_indicative = result.get('total_egp_indicative')
        self.calculated_at = timezone.now()

        by_code = {line['code']: line['amount'] for line in result['lines_eur']}
        self.shipping_eur = by_code.get('shipping', Decimal(0))
        self.eur1_eur = by_code.get('eur1', Decimal(0))
        self.shipping_extra_eur = by_code.get('shipping_type', Decimal(0))

        egp_by_code = {line['code']: line['amount'] for line in result['lines_egp']}
        self.port_fee_egp = egp_by_code.get('port', Decimal(0))
        self.showroom_fee_egp = egp_by_code.get('showroom', Decimal(0))

        plan = pricing.payment_plan(result, self.paid_eur or 0)
        self.deposit_covered = plan['deposit_covered']
        self.fully_paid = plan['fully_paid']
        self.remaining_eur = plan['remaining_eur']
        self.overpaid_eur = plan['overpaid_eur']

        self._pending_lines = result['lines_eur'] + result['lines_egp'] if save_lines else None
        return result

    def _zero_results(self):
        for field in ('net_eur', 'vat_reclaimable_eur', 'shipping_eur', 'admin_fee_eur',
                      'admin_fee_before_discount_eur', 'eur1_eur', 'shipping_extra_eur',
                      'total_eur', 'deposit_pct', 'deposit_eur', 'balance_eur',
                      'port_fee_egp', 'showroom_fee_egp', 'egp_due_on_arrival',
                      'remaining_eur', 'overpaid_eur'):
            setattr(self, field, Decimal(0))
        self.total_egp_indicative = None
        self.band_id = None
        self.band_label = ''
        self.deposit_covered = False
        self.fully_paid = False
        self._pending_lines = []

    #: Written by ``recalculate``, consumed by ``post_save``. Never touched in
    #: ``__init__`` — the serializer defers columns, so a partially loaded row
    #: must not pretend it has lines to write.
    _pending_lines = None

    # ── hooks ───────────────────────────────────────────────────────────────
    def pre_save(self):
        """Validation belongs here: this platform's write path never calls
        ``clean()`` (`modules/base/genie_serializer/write.py`), so a rule in
        ``clean`` is a rule that never runs."""
        if self.admin_fee_discount_eur and self.admin_fee_discount_eur < 0:
            raise ValidationError({'admin_fee_discount_eur': _(
                "A discount is a positive number. To charge more, change the band.")})
        if self.paid_eur and self.paid_eur < 0:
            raise ValidationError({'paid_eur': _("A payment cannot be negative.")})

        # Price first, then judge the result. Checking `total_eur` before the
        # calculator runs would reject a quote that is being created and
        # accepted in the same save — which is exactly what happens when a
        # salesman fills the form in front of a customer who says yes.
        self.recalculate()

        if self.state in ('sent', 'accepted') and not self.total_eur:
            raise ValidationError({'state': _(
                "There is no price yet. %(why)s") % {
                    'why': self.pricing_error or _("Enter the car's price with VAT.")}})

    def post_save(self):
        self._write_lines()

    def _write_lines(self):
        if self._pending_lines is None:
            return
        lines, self._pending_lines = self._pending_lines, None
        QuoteLine.all_objects.filter(quote_id=self.pk).delete()
        QuoteLine.all_objects.bulk_create([
            QuoteLine(quote_id=self.pk, sequence=(index + 1) * 10, code=line['code'],
                      label=line['label_ar'], amount=line['amount'], currency=line['currency'])
            for index, line in enumerate(lines)
        ])

    # ── buttons ─────────────────────────────────────────────────────────────
    @action
    def action_recalculate(queryset):
        """Re-run the calculator on today's bands, deliberately.

        A quote does not recalculate itself when a band changes — that is the
        whole point of freezing the figures. This is the button that says "yes,
        reprice this one", and the chatter records who pressed it.
        """
        repriced, refused = 0, []
        for quote in queryset:
            quote.save()
            if quote.pricing_error:
                refused.append(f"{quote.name or quote.pk}: {quote.pricing_error}")
            else:
                repriced += 1
        message = _("Repriced %(count)d quotation(s)") % {'count': repriced}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': True, 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_mark_sent(queryset):
        """Mark the offer as given to the customer."""
        sent, refused = 0, []
        for quote in queryset:
            if not quote.total_eur:
                refused.append(f"{quote.name or quote.pk}: {_('there is no price to send')}")
                continue
            quote.state = 'sent'
            quote.sent_at = timezone.now()
            quote.save()
            sent += 1
        message = _("Marked %(count)d quotation(s) as sent") % {'count': sent}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': True, 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_print_offer(queryset):
        """Open the offer as a page the salesman can print or save as PDF.

        Written as HTML rather than rendered through the PDF engine on purpose.
        The document is right-to-left Arabic, and a browser lays that out
        correctly with the fonts already on the machine — a PDF engine needs an
        embedded Arabic font and a shaping library, and gets the joins wrong
        when it does not have them. Ctrl+P from the tab produces the same PDF,
        with the text intact.
        """
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        from car_import.services import quote_document

        quote = queryset.first() if hasattr(queryset, 'first') else list(queryset)[0]
        if quote is None:
            return {'status': False, 'open_mode': 'message',
                    'message': _("Select a quotation first."), 'data': {}}
        if not quote.total_eur:
            return {'status': False, 'open_mode': 'message',
                    'message': quote.pricing_error or _("There is no price to print."),
                    'data': {}}

        html = quote_document.as_html(quote)
        safe_ref = (quote.name or f'quote-{quote.pk}').replace('/', '-')
        stamp = timezone.now().strftime('%Y%m%d%H%M%S')
        path = default_storage.save(f'car_import/quotes/{safe_ref}-{stamp}.html',
                                    ContentFile(html.encode('utf-8')))
        return {
            'status': True,
            # 'pdf' is this platform's "open it in a new tab" mode. The file
            # behind the URL is HTML, and the tab prints it the same way.
            'open_mode': 'pdf',
            'message': _("The offer is ready — print it or save it as PDF."),
            'data': {'pdf_url': default_storage.url(path),
                     'filename': f'{safe_ref}.html'},
        }

    @action
    def action_send_offer(queryset):
        """Send the offer to the customer on whatever channel they already use.

        Goes through the same omnichannel sender and the same kill switch as
        the stage messages. A quote is money, and money is the one subject this
        module refuses to let the AI handle — so this is a button a person
        presses, never something that fires on its own.
        """
        from car_import.services import quote_document, stage_notifier

        if not stage_notifier.messages_enabled():
            return {'status': False, 'open_mode': 'message', 'data': {},
                    'message': _("Customer messages are switched off "
                                 "(car_import.stage_messages_enabled).")}

        sent, refused = 0, []
        for quote in queryset:
            label = quote.name or quote.pk
            if not quote.total_eur:
                refused.append(f"{label}: {quote.pricing_error or _('no price yet')}")
                continue
            if quote.partner_id is None:
                refused.append(f"{label}: {_('no customer on this quotation')}")
                continue
            if stage_notifier.customer_opted_out(quote.partner):
                refused.append(f"{label}: {_('this customer asked not to be messaged')}")
                continue
            try:
                result = stage_notifier._send_free_text(
                    quote.partner, quote_document.as_text(quote)) or {}
            except Exception as exc:  # noqa: BLE001 — the outcome belongs in the message
                refused.append(f"{label}: {exc}")
                continue
            if result.get('success') is False or result.get('status') is False:
                refused.append(f"{label}: {result.get('error') or result.get('message') or 'send failed'}")
                continue
            quote.state = 'sent'
            quote.sent_at = timezone.now()
            quote.save()
            quote.message_post(body=_("The offer was sent to the customer."))
            sent += 1

        message = _("Sent %(count)d offer(s)") % {'count': sent}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': bool(sent), 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_accept(queryset):
        """The customer said yes — copy the total onto the deal."""
        accepted, refused = 0, []
        for quote in queryset:
            if not quote.total_eur:
                refused.append(f"{quote.name or quote.pk}: {_('there is no price to accept')}")
                continue
            quote.state = 'accepted'
            quote.save()
            # Copied, not linked. Renegotiating the quote afterwards must not
            # silently move the number somebody already signed under.
            if quote.deal_id:
                deal = quote.deal
                deal.amount_agreed = quote.total_eur
                deal.currency_note = 'EUR'
                deal.save()
            accepted += 1
        message = _("Accepted %(count)d quotation(s)") % {'count': accepted}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': True, 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}


class QuoteLine(BaseModel):
    """One row of the offer, exactly as the customer saw it."""

    all_objects = models.Manager()

    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='lines',
                              verbose_name=_("Quotation"))
    sequence = models.PositiveIntegerField(default=10, verbose_name=_("#"))
    code = models.CharField(max_length=32, verbose_name=_("Code"))
    label = models.CharField(max_length=190, verbose_name=_("Description"))
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                 verbose_name=_("Amount"))
    currency = models.CharField(max_length=8, default='EUR', verbose_name=_("Currency"))

    class Meta:
        verbose_name = _("Quotation line")
        verbose_name_plural = _("Quotation lines")
        ordering = ['sequence', 'id']

    def __str__(self):
        return f"{self.label} — {self.amount:,.2f} {self.currency}"
