# -*- coding: utf-8 -*-
"""The proforma invoice the assistant issues, and the payment a person confirms.

Two rows, and the line between them is the whole policy (`services/policy.py`):

* a **proforma invoice** is a request for money. The assistant writes it the
  moment a customer accepts a quotation — it states what is due now, to which
  account, against which offer. Nobody approves it, because it promises
  nothing the quotation did not already say;
* a **payment receipt** is a claim that money moved. The customer sends a
  screenshot, the assistant reads it and fills this row in, and then it
  *stops*: the row waits, `pending`, for the accountant. One button — Accept —
  is the only thing in the sale a person has to do, and it is the one thing a
  screenshot cannot prove. Accepting credits the quotation, marks the deal,
  tells the customer, and issues and sends the contract.

Amounts are a number next to a currency relation, never a money widget.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.base.decorators import action
from modules.base.fields import AttachmentForeignKeyField
from modules.base.models.base import BaseModel
from modules.base.models.managers import BranchAwareManager
from modules.base.models.mixins import BranchMixin, SequenceMixin
from modules.notifications.models.mixins import FullChatterMixin


class ProformaInvoice(SequenceMixin, BaseModel, BranchMixin, FullChatterMixin):
    """What the customer is asked to pay now, frozen as it was sent."""

    sequence_code = 'car_import.proforma'

    objects = BranchAwareManager()
    all_objects = models.Manager()

    _mail_track = {'state': None, 'paid_amount': None}

    STATE = [
        ('issued', _("Issued")),
        ('partly_paid', _("Partly paid")),
        ('paid', _("Paid")),
        ('cancelled', _("Cancelled")),
    ]

    name = models.CharField(max_length=32, blank=True, verbose_name=_("Reference"))
    state = models.CharField(max_length=16, choices=STATE, default='issued', verbose_name=_("Status"))
    partner = models.ForeignKey('base.Partner', on_delete=models.PROTECT,
                                related_name='car_proformas', verbose_name=_("Customer"))
    deal = models.ForeignKey('car_import.CarDeal', null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='proformas', verbose_name=_("Deal"))
    quote = models.ForeignKey('car_import.Quote', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='proformas', verbose_name=_("Quotation"))
    invoice_date = models.DateField(default=timezone.localdate, verbose_name=_("Date"))
    valid_until = models.DateField(null=True, blank=True, verbose_name=_("Valid until"))
    car_label = models.CharField(max_length=190, blank=True, verbose_name=_("Car"))

    currency = models.ForeignKey('base.Currency', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='+', verbose_name=_("Currency"))
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                       verbose_name=_("Total selling price"))
    deposit_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                      verbose_name=_("Deposit %"))
    amount_due = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name=_("Due now"),
        help_text=_("The deposit this invoice asks for. The balance follows the contract."))
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                      verbose_name=_("Confirmed so far"), editable=False)
    #: Frozen, like everything else a customer was shown. If the accountant
    #: changes the account next month, this still says where THIS customer was
    #: told to send the money.
    bank_details_text = models.TextField(blank=True, verbose_name=_("Bank details as sent"))

    document = models.FileField(upload_to='car_import/proformas/', blank=True,
                                verbose_name=_("Invoice file"), editable=False)
    issued_by_ai = models.BooleanField(default=False, verbose_name=_("Issued by the assistant"),
                                       editable=False)
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Sent at"), editable=False)
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Proforma invoice")
        verbose_name_plural = _("Proforma invoices")
        ordering = ['-id']
        indexes = [models.Index(fields=['state', 'invoice_date']), models.Index(fields=['partner'])]

    def __str__(self):
        return f"{self.name or '—'} · {self.amount_due:,.0f}"

    @property
    def remaining_due(self):
        return max((self.amount_due or Decimal(0)) - (self.paid_amount or Decimal(0)), Decimal(0))

    def pre_create(self):
        super().pre_create()
        if self.currency_id is None:
            from car_import.services import currencies
            self.currency = currencies.eur()

    def pre_save(self):
        super().pre_save()
        if self.amount_due is not None and self.amount_due < 0:
            raise ValidationError({'amount_due': _("An invoice cannot ask for a negative amount.")})

    def refresh_paid(self):
        """Recompute what has been confirmed against this invoice."""
        paid = sum((r.amount_credited or Decimal(0))
                   for r in self.receipts.filter(state='accepted'))
        self.paid_amount = paid
        if self.state != 'cancelled':
            self.state = ('paid' if self.amount_due and paid >= self.amount_due
                          else 'partly_paid' if paid > 0 else 'issued')
        self.save()

    @action
    def action_open_document(queryset):
        """Open the invoice file."""
        invoice = queryset.first() if hasattr(queryset, 'first') else list(queryset)[0]
        if invoice is None or not invoice.document:
            return {'status': False, 'open_mode': 'message', 'data': {},
                    'message': _("This invoice has no file yet.")}
        return {'status': True, 'open_mode': 'pdf', 'message': _("The invoice is ready."),
                'data': {'pdf_url': invoice.document.url,
                         'filename': invoice.document.name.rsplit('/', 1)[-1]}}

    @action
    def action_resend(queryset):
        """Send the invoice to the customer again."""
        from car_import.services import sales_flow
        sent, refused = 0, []
        for invoice in queryset:
            outcome = sales_flow.send_proforma(invoice)
            if outcome.get('sent'):
                sent += 1
            else:
                refused.append(f"{invoice.name or invoice.pk}: {outcome.get('error') or 'send failed'}")
        message = _("Sent %(count)d invoice(s)") % {'count': sent}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': bool(sent), 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_cancel(queryset):
        """Cancel an invoice instead of deleting it."""
        cancelled = 0
        for invoice in queryset:
            if invoice.state in ('cancelled', 'paid'):
                continue
            invoice.state = 'cancelled'
            invoice.save()
            cancelled += 1
        return {'status': bool(cancelled), 'open_mode': 'message',
                'message': _("Cancelled %(count)d invoice(s)") % {'count': cancelled},
                'data': {}, 'on_success': {'type': 'refresh'}}


class PaymentReceipt(SequenceMixin, BaseModel, BranchMixin, FullChatterMixin):
    """One transfer the customer says they made, waiting for the accountant."""

    sequence_code = 'car_import.receipt'

    objects = BranchAwareManager()
    all_objects = models.Manager()

    _mail_track = {'state': None, 'amount_credited': None}

    STATE = [
        ('pending', _("Waiting for the accountant")),
        ('accepted', _("Accepted — money received")),
        ('rejected', _("Rejected")),
    ]
    CONFIDENCE = [
        ('high', _("Clear")),
        ('medium', _("Readable, check it")),
        ('low', _("Hard to read")),
    ]
    SOURCE = [('ai', _("Read by the assistant")), ('manual', _("Entered by a person"))]

    name = models.CharField(max_length=32, blank=True, verbose_name=_("Reference"))
    state = models.CharField(max_length=16, choices=STATE, default='pending', verbose_name=_("Status"))
    source = models.CharField(max_length=8, choices=SOURCE, default='manual', verbose_name=_("Source"),
                              editable=False)
    partner = models.ForeignKey('base.Partner', on_delete=models.PROTECT,
                                related_name='car_payment_receipts', verbose_name=_("Customer"))
    deal = models.ForeignKey('car_import.CarDeal', null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='payment_receipts', verbose_name=_("Deal"))
    quote = models.ForeignKey('car_import.Quote', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='payment_receipts', verbose_name=_("Quotation"))
    proforma = models.ForeignKey(ProformaInvoice, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='receipts', verbose_name=_("Proforma invoice"))
    conversation_ref = models.CharField(max_length=64, blank=True, verbose_name=_("Conversation"),
                                        editable=False)

    # ── what the screenshot says ────────────────────────────────────────────
    screenshot = AttachmentForeignKeyField(
        related_name='+', upload_to='car_import/receipts',
        allowed_types=['image', 'pdf', 'document'], verbose_name=_("Transfer screenshot"))
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                 verbose_name=_("Amount on the screenshot"))
    currency = models.ForeignKey('base.Currency', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='+', verbose_name=_("Its currency"))
    transfer_date = models.DateField(null=True, blank=True, verbose_name=_("Transfer date"))
    sender_name = models.CharField(max_length=190, blank=True, verbose_name=_("Sent by"))
    bank_name = models.CharField(max_length=128, blank=True, verbose_name=_("Bank"))
    bank_reference = models.CharField(max_length=128, blank=True, verbose_name=_("Transfer reference"))
    ai_confidence = models.CharField(max_length=8, choices=CONFIDENCE, blank=True,
                                     verbose_name=_("How clear it was"))
    ai_remarks = models.TextField(
        blank=True, verbose_name=_("What to check"),
        help_text=_("Anything that did not match: the amount against the invoice, the name "
                    "against the customer, a date in the future"))

    # ── what the accountant confirms ────────────────────────────────────────
    amount_credited = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name=_("Amount to credit (EUR)"),
        help_text=_("What reaches the deal when you accept. Correct it if the bank statement "
                    "says otherwise — this is the number that counts"))
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+',
                                    verbose_name=_("Confirmed by"), editable=False)
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Confirmed at"),
                                       editable=False)
    reject_reason = models.CharField(max_length=255, blank=True, verbose_name=_("Why it was rejected"))
    contract_outcome = models.CharField(max_length=255, blank=True,
                                        verbose_name=_("What happened to the contract"),
                                        editable=False)
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Payment receipt")
        verbose_name_plural = _("Payment receipts")
        ordering = ['-id']
        indexes = [models.Index(fields=['state']), models.Index(fields=['partner'])]

    def __str__(self):
        amount = f'{self.amount_credited or self.amount or 0:,.0f}'
        return f"{self.name or '—'} · {amount}"

    def pre_create(self):
        super().pre_create()
        if self.currency_id is None:
            from car_import.services import currencies
            self.currency = currencies.eur()
        if self.deal_id and self.partner_id is None:
            self.partner_id = self.deal.partner_id

    def pre_save(self):
        super().pre_save()
        for field in ('amount', 'amount_credited'):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise ValidationError({field: _("A payment cannot be negative.")})

    # ── the one button ──────────────────────────────────────────────────────
    @action
    def action_accept(queryset):
        """The money arrived. Credit it, tell the customer, issue the contract."""
        from car_import.services import sales_flow

        done, refused, lines = 0, [], []
        for receipt in queryset:
            label = receipt.name or receipt.pk
            try:
                outcome = sales_flow.accept_receipt(
                    receipt, user=getattr(getattr(receipt, 'env', None), 'user', None))
            except ValidationError as exc:
                refused.append(f"{label}: {'; '.join(exc.messages)}")
                continue
            except Exception as exc:  # noqa: BLE001 — the reason belongs on screen
                refused.append(f"{label}: {exc}")
                continue
            done += 1
            lines.append(f"{label}: {outcome.get('summary', '')}")
        message = _("Accepted %(count)d payment(s)") % {'count': done}
        if lines:
            message += "\n" + "\n".join(lines)
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': bool(done), 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_reject(queryset):
        """This is not a payment we received. Nothing is credited."""
        from car_import.services import sales_flow

        rejected = 0
        for receipt in queryset:
            if receipt.state != 'pending':
                continue
            sales_flow.reject_receipt(
                receipt, user=getattr(getattr(receipt, 'env', None), 'user', None))
            rejected += 1
        return {'status': bool(rejected), 'open_mode': 'message',
                'message': _("Rejected %(count)d receipt(s)") % {'count': rejected},
                'data': {}, 'on_success': {'type': 'refresh'}}
