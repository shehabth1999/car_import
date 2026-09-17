# -*- coding: utf-8 -*-
"""Contracts: the lawyer's document, filled from the deal.

Two models, and the split matters. A **template** is the lawyer's file with
named blanks — it changes rarely, and when it does a lawyer changed it. A
**contract** is one filled copy for one deal, and once it is generated it is
evidence: the file is kept, not regenerated, because the customer is holding a
printout of the version that existed on the day they signed.

That is the same rule the quotation follows, for the same reason. Regenerating
a document from today's data is how a company ends up unable to prove what it
agreed to.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.base.decorators import action, onchange
from modules.base.fields import AttachmentForeignKeyField
from modules.base.models.base import BaseModel
from modules.base.models.managers import BranchAwareManager
from modules.base.models.mixins import BranchMixin
from modules.notifications.models.mixins import FullChatterMixin


class ContractIssuer(BaseModel):
    """K&T's legal identity, as the contract prints it.

    It lives here rather than inside the Word file because **the signatory
    changes**. Today the templates carry one authorised signatory's name and
    national ID as literal text, so the day somebody else signs, the contract
    has to be edited by whoever owns the .docx — and the version that goes out
    in the meantime names a person who did not sign it.

    The register and tax-card numbers are here for the opposite reason: they
    never change, and having them in one row means a contract, an offer sheet
    and a power of attorney cannot disagree about them.
    """

    code = models.CharField(max_length=32, unique=True, default='kt',
                            verbose_name=_("Code"))
    name = models.CharField(max_length=190, verbose_name=_("Company name"))
    name_en = models.CharField(max_length=190, blank=True, verbose_name=_("Company name (English)"))
    commercial_register = models.CharField(max_length=64, blank=True,
                                           verbose_name=_("Commercial register"))
    chamber = models.CharField(max_length=128, blank=True, verbose_name=_("Chamber of commerce"))
    tax_card = models.CharField(max_length=64, blank=True, verbose_name=_("Tax card"))
    represents = models.CharField(max_length=190, blank=True,
                                  verbose_name=_("Marketing agent for"))
    legal_rep_name = models.CharField(max_length=190, blank=True,
                                      verbose_name=_("Legal representative"))
    legal_rep_national_id = models.CharField(max_length=32, blank=True,
                                             verbose_name=_("Their national ID"))
    email = models.EmailField(blank=True, verbose_name=_("Notice email"))
    address = models.CharField(max_length=255, blank=True, verbose_name=_("Address"))
    is_default = models.BooleanField(default=True, verbose_name=_("Use by default"))

    class Meta:
        verbose_name = _("Contract issuer")
        verbose_name_plural = _("Contract issuers")
        ordering = ['code']

    def __str__(self):
        return self.name or self.code

    @classmethod
    def default(cls):
        return (cls.objects.filter(is_default=True).order_by('code').first()
                or cls.objects.order_by('code').first())


class ContractSignatory(BaseModel):
    """Somebody authorised to sign, and the dates they were authorised for.

    Dated on purpose. "Who could sign in March?" is a question that gets asked
    exactly once, by a lawyer, about a contract that is already disputed.
    """

    issuer = models.ForeignKey(ContractIssuer, on_delete=models.CASCADE,
                               related_name='signatories', verbose_name=_("Issuer"))
    name = models.CharField(max_length=190, verbose_name=_("Name"))
    national_id = models.CharField(max_length=32, blank=True, verbose_name=_("National ID"))
    title = models.CharField(max_length=128, blank=True, verbose_name=_("Capacity"))
    authorised_from = models.DateField(null=True, blank=True, verbose_name=_("Authorised from"))
    authorised_to = models.DateField(null=True, blank=True, verbose_name=_("Authorised until"))
    is_default = models.BooleanField(default=False, verbose_name=_("Signs by default"))

    class Meta:
        verbose_name = _("Authorised signatory")
        verbose_name_plural = _("Authorised signatories")
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name

    @classmethod
    def in_force(cls, issuer=None, on=None):
        from django.db.models import Q
        when = on or timezone.localdate()
        rows = cls.objects.filter(issuer=issuer) if issuer else cls.objects.all()
        return (rows.filter(Q(authorised_from__isnull=True) | Q(authorised_from__lte=when))
                .filter(Q(authorised_to__isnull=True) | Q(authorised_to__gte=when)))


class ContractTemplate(BaseModel):
    """One of the client's contracts, with its blanks turned into fields."""

    PROGRAM = [
        ('personal', _("Personal import")),
        ('initiative', _("Initiative")),
        ('commercial', _("Commercial import")),
        ('any', _("Any programme")),
    ]

    code = models.CharField(max_length=64, unique=True, verbose_name=_("Code"))
    name = models.CharField(max_length=190, verbose_name=_("Name"))
    program = models.CharField(max_length=24, choices=PROGRAM, default='any',
                               verbose_name=_("Programme"))
    docx = models.FileField(upload_to='car_import/contract_templates/',
                            verbose_name=_("Template file"))
    source_filename = models.CharField(max_length=255, blank=True,
                                       verbose_name=_("Original filename"))
    #: False for the copies the lawyer sent as reference rather than as the
    #: fill-in master. They are kept because "why does this clause differ?" is
    #: a question somebody asks eventually.
    is_fillable = models.BooleanField(default=True, verbose_name=_("Can be filled"))
    tokens = models.JSONField(default=list, blank=True, verbose_name=_("Fields in this template"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Contract template")
        verbose_name_plural = _("Contract templates")
        ordering = ['program', 'code']

    def __str__(self):
        return self.name or self.code


class Contract(BaseModel, BranchMixin, FullChatterMixin):
    """One filled contract for one deal."""

    objects = BranchAwareManager()
    all_objects = models.Manager()

    _mail_track = {'state': None}

    STATE = [
        ('draft', _("Draft")),
        ('generated', _("Generated")),
        ('signed', _("Signed")),
        ('cancelled', _("Cancelled")),
    ]

    deal = models.ForeignKey('car_import.CarDeal', on_delete=models.CASCADE,
                             related_name='contracts', verbose_name=_("Deal"))
    template = models.ForeignKey(ContractTemplate, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='contracts',
                                 verbose_name=_("Template"))
    quote = models.ForeignKey('car_import.Quote', null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='contracts',
                              verbose_name=_("Quotation"))
    issuer = models.ForeignKey(ContractIssuer, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='contracts', verbose_name=_("Issued by"))
    signatory = models.ForeignKey(ContractSignatory, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name='contracts',
                                  verbose_name=_("Signed for the company by"))
    state = models.CharField(max_length=16, choices=STATE, default='draft',
                             verbose_name=_("Status"))

    contract_date = models.DateField(default=timezone.localdate, verbose_name=_("Contract date"))
    # What the customer's ID says, which is not always what the CRM record says
    # — and the contract has to match the ID, not the nickname in the chat.
    customer_name = models.CharField(max_length=190, blank=True,
                                     verbose_name=_("Name as on the ID"))
    customer_national_id = models.CharField(max_length=32, blank=True,
                                            verbose_name=_("National ID number"))
    customer_address = models.CharField(max_length=255, blank=True, verbose_name=_("Address"))
    customer_email = models.EmailField(blank=True, verbose_name=_("Email"))
    shipping_name = models.CharField(
        max_length=190, blank=True, verbose_name=_("Ships in the name of"),
        help_text=_("Usually the customer. On the initiative route it may be the "
                    "initiative holder instead"))

    car_model = models.CharField(max_length=128, blank=True, verbose_name=_("Model"))
    car_trim = models.CharField(max_length=128, blank=True, verbose_name=_("Trim"))
    car_model_year = models.CharField(max_length=8, blank=True, verbose_name=_("Model year"))
    car_configuration = models.CharField(max_length=128, blank=True,
                                         verbose_name=_("Configuration number"))

    currency = models.ForeignKey('base.Currency', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='+', verbose_name=_("Currency"))
    total_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                    verbose_name=_("Total contract value (EUR)"))
    down_payment_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           verbose_name=_("Received at signing (EUR)"))
    bank_transfer_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                            verbose_name=_("Bank transfer (EUR)"))
    cash_on_bl_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                         verbose_name=_("Cash on bill of lading (EUR)"))
    deposit_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                      verbose_name=_("Deposit %"))

    instalment_1_date = models.DateField(null=True, blank=True, verbose_name=_("Payment 1 — date"))
    instalment_1_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                              verbose_name=_("Payment 1 — amount"))
    instalment_2_date = models.DateField(null=True, blank=True, verbose_name=_("Payment 2 — date"))
    instalment_2_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                              verbose_name=_("Payment 2 — amount"))
    instalment_3_date = models.DateField(null=True, blank=True, verbose_name=_("Payment 3 — date"))
    instalment_3_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                              verbose_name=_("Payment 3 — amount"))

    document = models.FileField(upload_to='car_import/contracts/', blank=True,
                                verbose_name=_("Generated contract"), editable=False)
    generated_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Generated at"),
                                        editable=False)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+',
                                     verbose_name=_("Generated by"), editable=False)
    signed_on = models.DateField(null=True, blank=True, verbose_name=_("Signed on"))
    #: The copy that came back with a signature on it. A generated file proves
    #: what we offered; only this proves what they agreed to.
    signed_document = AttachmentForeignKeyField(
        related_name='+',
        upload_to='car_import/contracts/signed', allowed_types=['pdf', 'image', 'document'],
        verbose_name=_("Signed copy"))
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Sent at"),
                                   editable=False)
    void_reason = models.CharField(max_length=255, blank=True, verbose_name=_("Why it was voided"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Contract")
        verbose_name_plural = _("Contracts")
        ordering = ['-id']

    def __str__(self):
        return f'{self.deal.name if self.deal_id else "—"} · {self.get_state_display()}'

    # ── the fields the template asks for ────────────────────────────────────
    #: Without these the document is not a contract, it is a form with gaps.
    #: `generate()` refuses rather than producing one.
    REQUIRED_TOKENS = (
        'customer_name', 'customer_national_id',
        'car_model', 'contract_total_eur', 'deposit_pct',
    )

    def values(self):
        """Every token the template can ask for, as text ready to print."""
        date = self.contract_date or timezone.localdate()
        issuer = self.issuer or ContractIssuer.default()
        signatory = self.signatory or (
            ContractSignatory.in_force(issuer, on=date).order_by('-is_default').first()
            if issuer else None)
        return {
            # The company side, from a row rather than from the Word file — the
            # signatory changes, and a contract naming somebody who did not sign
            # it is a contract with a hole in it.
            'issuer_name': getattr(issuer, 'name', '') or '',
            'issuer_register': getattr(issuer, 'commercial_register', '') or '',
            'issuer_tax_card': getattr(issuer, 'tax_card', '') or '',
            'issuer_legal_rep': getattr(issuer, 'legal_rep_name', '') or '',
            'issuer_legal_rep_id': getattr(issuer, 'legal_rep_national_id', '') or '',
            'issuer_email': getattr(issuer, 'email', '') or '',
            'signatory_name': getattr(signatory, 'name', '') or '',
            'signatory_national_id': getattr(signatory, 'national_id', '') or '',
            'contract_day': f'{date.day:02d}',
            'contract_month': f'{date.month:02d}',
            'contract_year': str(date.year),
            'customer_name': self.customer_name,
            'customer_national_id': self.customer_national_id,
            'customer_address': self.customer_address,
            'customer_email': self.customer_email,
            'shipping_name': self.shipping_name or self.customer_name,
            'car_model': self.car_model,
            'car_trim': self.car_trim,
            'car_model_year': self.car_model_year,
            'car_configuration': self.car_configuration,
            'contract_total_eur': _amount(self.total_eur),
            'contract_down_payment_eur': _amount(self.down_payment_eur),
            'contract_balance_eur': _amount(self.total_eur - self.down_payment_eur),
            'contract_bank_transfer_eur': _amount(self.bank_transfer_eur),
            'contract_cash_on_bl_eur': _amount(self.cash_on_bl_eur),
            'deposit_pct': f'{float(self.deposit_pct):g}',
            'instalment_1_date': _date(self.instalment_1_date),
            'instalment_2_date': _date(self.instalment_2_date),
            'instalment_3_date': _date(self.instalment_3_date),
            'instalment_1_amount': _amount(self.instalment_1_amount),
            'instalment_2_amount': _amount(self.instalment_2_amount),
            'instalment_3_amount': _amount(self.instalment_3_amount),
        }

    def prefill_from_deal(self):
        """Copy what the deal and its accepted quotation already know."""
        deal = self.deal
        partner = getattr(deal, 'partner', None)
        vehicle = getattr(deal, 'vehicle', None)

        self.customer_name = self.customer_name or (getattr(partner, 'name', '') or '')
        self.customer_email = self.customer_email or (getattr(partner, 'email', '') or '')
        # Clause: "وشحنها باسم السيد/…". On a provided initiative the car ships
        # in the HOLDER's name, not the buyer's — that is the whole mechanism of
        # the L5 line, and getting it wrong puts the wrong person on a customs
        # document.
        holder = getattr(getattr(deal, 'initiative', None), 'holder', None)
        self.shipping_name = (self.shipping_name
                              or (getattr(holder, 'name', '') if holder else '')
                              or self.customer_name)
        if vehicle is not None:
            self.car_model = self.car_model or f'{vehicle.make} {vehicle.model}'.strip()
            self.car_trim = self.car_trim or (vehicle.trim or '')
            self.car_model_year = self.car_model_year or str(vehicle.model_year or '')

        quote = self.quote or deal.quotes.filter(state='accepted').order_by('-id').first()
        if quote is not None:
            self.quote = quote
            self.total_eur = self.total_eur or quote.total_eur
            self.deposit_pct = self.deposit_pct or quote.deposit_pct
            self.down_payment_eur = self.down_payment_eur or quote.deposit_eur
        # The deal's own contract figures win when somebody typed them: they are
        # what the accountant agreed, and a quotation is only an offer.
        for field, source in (('total_eur', 'contract_total_eur'),
                              ('down_payment_eur', 'contract_down_payment_eur'),
                              ('bank_transfer_eur', 'contract_bank_transfer_eur'),
                              ('cash_on_bl_eur', 'contract_cash_on_bl_eur')):
            value = getattr(deal, source, None)
            if value:
                setattr(self, field, value)
        if self.issuer_id is None:
            self.issuer = ContractIssuer.default()
        if self.signatory_id is None and self.issuer_id:
            self.signatory = (ContractSignatory.in_force(self.issuer)
                              .order_by('-is_default').first())
        if self.template_id is None:
            self.template = (ContractTemplate.objects
                             .filter(is_fillable=True)
                             .filter(models.Q(program=deal.program) | models.Q(program='any'))
                             .order_by('program').first())

    def pre_create(self):
        super().pre_create()
        self.prefill_from_deal()
        if self.currency_id is None:
            from car_import.services import currencies
            self.currency = currencies.eur()

    # ── live reactions on the form ──────────────────────────────────────────
    @onchange('deal')
    def _onchange_deal(self):
        if self.deal_id:
            self.prefill_from_deal()

    def _live_sum(self):
        total = self.total_eur or 0
        parts = (self.down_payment_eur or 0) + (self.bank_transfer_eur or 0) + (self.cash_on_bl_eur or 0)
        if total and parts and parts != total:
            return {'errors': {'cash_on_bl_eur': str(_(
                "The payments (%(parts)s €) do not add up to the contract total (%(total)s €).")
                % {'parts': f'{parts:,.2f}', 'total': f'{total:,.2f}'})}}
        return {'errors': {}}

    @onchange('total_eur')
    def _onchange_total(self):
        return self._live_sum()

    @onchange('down_payment_eur')
    def _onchange_down(self):
        return self._live_sum()

    @onchange('bank_transfer_eur')
    def _onchange_bank(self):
        return self._live_sum()

    @onchange('cash_on_bl_eur')
    def _onchange_cash(self):
        return self._live_sum()

    def pre_save(self):
        super().pre_save()
        total = self.total_eur or 0
        parts = (self.down_payment_eur or 0) + (self.bank_transfer_eur or 0) \
            + (self.cash_on_bl_eur or 0)
        # A contract whose three payment lines do not add up to its own total is
        # the argument that happens six weeks later, in writing, with a lawyer.
        if total and parts and parts != total:
            raise ValidationError({'cash_on_bl_eur': _(
                "The payments (%(parts)s €) do not add up to the contract total "
                "(%(total)s €).") % {'parts': f'{parts:,.2f}', 'total': f'{total:,.2f}'}})

    # ── producing the document ──────────────────────────────────────────────
    def generate(self, user=None):
        from django.core.files.base import ContentFile

        from car_import.services import contract_docx

        if self.template_id is None or not self.template.docx:
            raise ValidationError(_("No contract template is set for this programme. "
                                    "Import them with `import_contract_templates`."))
        self.template.docx.open('rb')
        try:
            source = self.template.docx.read()
        finally:
            self.template.docx.close()

        filled, leftover = contract_docx.fill(source, self.values(),
                                              required=self.REQUIRED_TOKENS)
        reference = (self.deal.name or f'deal-{self.deal_id}').replace('/', '-')
        stamp = timezone.now().strftime('%Y%m%d%H%M%S')
        self.document.save(f'{reference}-{stamp}.docx', ContentFile(filled), save=False)
        self.generated_at = timezone.now()
        self.generated_by = user
        self.state = 'generated'
        self.save()
        return leftover

    @action
    def action_generate_contract(queryset):
        """Fill the template and attach the document."""
        made, refused = 0, []
        for contract in queryset:
            try:
                leftover = contract.generate(user=getattr(contract, 'env', None)
                                             and contract.env.user or None)
            except Exception as exc:  # noqa: BLE001 — the reason belongs on screen
                refused.append(f'{contract.deal.name if contract.deal_id else contract.pk}: {exc}')
                continue
            made += 1
            if leftover:
                contract.message_post(body=_(
                    "Generated with these fields left blank: %(fields)s")
                    % {'fields': ', '.join(leftover)})
        message = _("Generated %(count)d contract(s)") % {'count': made}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': bool(made), 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_send_contract(queryset):
        """Send the generated contract to the customer on their own channel.

        Behind a confirmation and the same kill switch as every other outbound
        message. A contract is the most consequential thing this system can put
        in front of a customer, so nothing sends it on a schedule or a trigger.
        """
        from car_import.services import stage_notifier

        if not stage_notifier.messages_enabled():
            return {'status': False, 'open_mode': 'message', 'data': {},
                    'message': _("Customer messages are switched off.")}

        sent, refused = 0, []
        for contract in queryset:
            label = contract.deal.name if contract.deal_id else contract.pk
            partner = getattr(contract.deal, 'partner', None)
            if not contract.document:
                refused.append(f'{label}: {_("generate it first")}')
                continue
            if partner is None:
                refused.append(f'{label}: {_("no customer on this deal")}')
                continue
            try:
                from modules.chat.services.omnichannel_send_service import OmnichannelSendService
                result = OmnichannelSendService().send_and_broadcast(
                    partner, {'url': contract.document.url},
                    message_type='document',
                    filename=contract.document.name.rsplit('/', 1)[-1],
                    caption=_("عقد الاستيراد — برجاء المراجعة والتوقيع")) or {}
            except Exception as exc:  # noqa: BLE001 — the reason belongs on screen
                refused.append(f'{label}: {exc}')
                continue
            if result.get('success') is False or result.get('status') is False:
                refused.append(f'{label}: {result.get("error") or "send failed"}')
                continue
            contract.sent_at = timezone.now()
            contract.save()
            contract.message_post(body=_("The contract was sent to the customer."))
            sent += 1

        message = _("Sent %(count)d contract(s)") % {'count': sent}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': bool(sent), 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_void(queryset):
        """Void a contract instead of deleting it.

        Nothing is ever deleted here. A voided contract is the evidence that a
        version existed and was withdrawn, which is exactly the question asked
        when two copies of a contract turn up with different numbers on them.
        """
        voided = 0
        for contract in queryset:
            if contract.state == 'cancelled':
                continue
            contract.state = 'cancelled'
            contract.save()
            contract.message_post(body=_("Contract voided. The file is kept."))
            voided += 1
        return {'status': bool(voided), 'open_mode': 'message',
                'message': _("Voided %(count)d contract(s)") % {'count': voided},
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_print_annex2(queryset):
        """Annex 2 — the vehicle specification, as a printable page."""
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        from car_import.services import contract_annex

        contract = queryset.first() if hasattr(queryset, 'first') else list(queryset)[0]
        if contract is None or contract.deal_id is None:
            return {'status': False, 'open_mode': 'message', 'data': {},
                    'message': _("Select a contract first.")}
        vehicle = getattr(contract.deal, 'vehicle', None)
        if vehicle is None:
            return {'status': False, 'open_mode': 'message', 'data': {},
                    'message': _("This deal has no car, so there is nothing to specify.")}

        html = contract_annex.as_html(contract, vehicle)
        reference = (contract.deal.name or f'contract-{contract.pk}').replace('/', '-')
        stamp = timezone.now().strftime('%Y%m%d%H%M%S')
        path = default_storage.save(f'car_import/annexes/{reference}-annex2-{stamp}.html',
                                    ContentFile(html.encode('utf-8')))
        return {'status': True, 'open_mode': 'pdf',
                'message': _("Annex 2 is ready."),
                'data': {'pdf_url': default_storage.url(path),
                         'filename': f'{reference}-annex2.html'}}

    @action
    def action_mark_signed(queryset):
        """Record that the customer signed."""
        signed = 0
        for contract in queryset:
            # A signature needs a document to be on. Marking a contract signed
            # with nothing generated records an agreement to nothing.
            if not contract.document:
                continue
            contract.state = 'signed'
            contract.signed_on = timezone.localdate()
            contract.save()
            signed += 1
        return {'status': bool(signed), 'open_mode': 'message',
                'message': _("Marked %(count)d contract(s) as signed") % {'count': signed},
                'data': {}, 'on_success': {'type': 'refresh'}}


def _amount(value):
    return f'{(value or 0):,.2f}'


def _date(value):
    return value.strftime('%d / %m / %Y') if value else ''
