# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.base.decorators import action, onchange
from modules.base.fields import AttachmentForeignKeyField
from modules.base.models.base import BaseModel
from modules.base.models.managers import BranchAwareManager
from modules.base.models.mixins import BranchMixin, SequenceMixin
from modules.notifications.models.mixins import FullChatterMixin


class CarDeal(SequenceMixin, BaseModel, BranchMixin, FullChatterMixin):
    """
    One car for one customer, moving through the client's 13 shipping stages.

    This is our own model on purpose (decision D24): the sales order would have
    dragged in `account`, `payment` and `products` plus three self-installing
    bridges, for a lifecycle this business does not use. Money appears here only
    as a mark a human sets — there is no invoice, no journal entry, no ledger.
    """

    sequence_code = 'car_import.cardeal'

    objects = BranchAwareManager()
    all_objects = models.Manager()

    #: Changes to these land in the chatter automatically.
    _mail_track = {
        'import_stage': None,
        'state': None,
        'payment_state': None,
        'assigned_to': None,
        'financing_type': None,
    }

    STATE = [
        ('open', _("Open")),
        ('on_hold', _("On hold")),
        ('done', _("Delivered")),
        ('cancelled', _("Cancelled")),
    ]
    PROGRAM = [
        ('initiative', _("Initiative (المبادرة)")),
        ('personal', _("Personal import")),
        ('commercial', _("Commercial import")),
        ('first_owner', _("First owner")),
        ('showroom', _("Showroom car in Egypt")),
        ('shipping_only', _("Shipping only")),
        # L6. It was one of the client's six revenue lines and the only one with
        # no route through this system at all.
        ('consignment', _("Consignment (وساطة)")),
    ]
    PAYMENT_STATE = [
        ('not_paid', _("Not paid")),
        ('deposit_paid', _("Deposit paid")),
        ('partially_paid', _("Partly paid")),
        ('fully_paid', _("Fully paid")),
    ]
    FINANCING_TYPE = [
        ('cash', _("Cash")),
        ('direct_instalments', _("Company instalments")),
        ('bank', _("Bank financing (cars in Egypt)")),
    ]

    # ── identity ────────────────────────────────────────────────────────────
    name = models.CharField(max_length=32, blank=True, verbose_name=_("Reference"))
    partner = models.ForeignKey(
        'base.Partner', on_delete=models.PROTECT,
        related_name='car_deals', verbose_name=_("Customer"),
    )
    lead = models.ForeignKey(
        'crm.Lead', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='car_deals', verbose_name=_("Lead"),
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='car_deals', verbose_name=_("Sales agent"),
    )
    state = models.CharField(max_length=16, choices=STATE, default='open', verbose_name=_("Status"))
    hold_reason = models.CharField(max_length=255, blank=True, verbose_name=_("Reason for hold"))
    cancel_reason = models.CharField(max_length=255, blank=True, verbose_name=_("Reason for cancelling"))

    # ── what is being imported ──────────────────────────────────────────────
    vehicle = models.ForeignKey(
        'car_import.Vehicle', null=True, blank=True, on_delete=models.PROTECT,
        related_name='car_deals', verbose_name=_("Car"),
    )
    program = models.CharField(max_length=24, choices=PROGRAM, default='initiative', verbose_name=_("Programme"))
    #: The plan's "Subject" row. The initiative knew about the deal and the
    #: deal did not know about the initiative, which meant the contract clause
    #: "shipped in the name of" — `initiative.holder` on a provided initiative,
    #: the customer otherwise — could not be answered from the deal at all.
    initiative = models.ForeignKey(
        'car_import.Initiative', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='deals', verbose_name=_("Initiative"))
    accepted_quote = models.ForeignKey(
        'car_import.Quote', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='accepted_on', verbose_name=_("Accepted quotation"))
    customer_is_initiative_holder = models.BooleanField(
        default=False, verbose_name=_("The customer holds the initiative"),
        help_text=_("Customs clearance happens in the customer's name, so the company has "
                    "no sale lien — instalments are not available (client, 2026-09-14)"),
    )

    # ── stage ───────────────────────────────────────────────────────────────
    import_stage = models.ForeignKey(
        'car_import.ImportStage', null=True, blank=True, on_delete=models.PROTECT,
        related_name='deals', verbose_name=_("Stage"),
    )
    stage_entered_at = models.DateTimeField(null=True, blank=True, verbose_name=_("In this stage since"))
    previous_stage = models.ForeignKey(
        'car_import.ImportStage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_("Previous stage"),
    )
    stage_is_blocked = models.BooleanField(default=False, verbose_name=_("Blocked"))
    blocked_reason = models.CharField(max_length=255, blank=True, verbose_name=_("Why it is blocked"))
    notifications_suppressed = models.BooleanField(
        default=False, verbose_name=_("Hold customer messages"),
        help_text=_("On while migrating or bulk-loading, so nobody is messaged by accident"),
    )

    # ── the payment mark — informational only, never accounting ─────────────
    payment_state = models.CharField(
        max_length=24, choices=PAYMENT_STATE, default='not_paid', verbose_name=_("Payment"),
    )
    amount_agreed = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                        verbose_name=_("Agreed amount"))
    amount_paid_marked = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                             verbose_name=_("Marked as paid"))
    amount_due_marked = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                            verbose_name=_("Marked as due"))
    currency_note = models.CharField(max_length=32, blank=True, verbose_name=_("Currency"))
    payment_marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_("Marked by"),
    )
    payment_marked_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Marked at"))
    payment_note = models.CharField(max_length=255, blank=True, verbose_name=_("Note"))

    # ── financing — the plan agreed, not a schedule ─────────────────────────
    financing_type = models.CharField(max_length=24, choices=FINANCING_TYPE, default='cash',
                                      verbose_name=_("Payment plan"))
    financing_down_payment_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                                     default=50, verbose_name=_("Down payment %"))
    financing_term_months = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Term (months)"))
    financing_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                             default=27, verbose_name=_("Rate % a year (flat)"))
    financing_bank = models.CharField(max_length=128, blank=True, verbose_name=_("Bank"))
    cheques_received = models.BooleanField(default=False, verbose_name=_("All cheques received"))
    financing_note = models.CharField(max_length=255, blank=True, verbose_name=_("Financing note"))

    # ── contract amounts, printed on the contract ───────────────────────────
    contract_date = models.DateField(null=True, blank=True, verbose_name=_("Contract date"))
    contract_total_eur = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                             verbose_name=_("Contract total (EUR)"))
    contract_down_payment_eur = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                                    verbose_name=_("Received at signing (EUR)"))
    contract_bank_transfer_eur = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                                     verbose_name=_("Bank transfer (EUR)"))
    contract_cash_on_bl_eur = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                                  verbose_name=_("Cash on bill of lading (EUR)"))

    # ── logistics ───────────────────────────────────────────────────────────
    acid_number = models.CharField(max_length=64, blank=True, verbose_name=_("ACID number"))
    import_approval_number = models.CharField(max_length=64, blank=True, verbose_name=_("Import approval"))
    carrier = models.CharField(max_length=128, blank=True, verbose_name=_("Carrier"))
    vessel = models.CharField(max_length=128, blank=True, verbose_name=_("Vessel"))
    booking_ref = models.CharField(max_length=64, blank=True, verbose_name=_("Booking"))
    sail_date = models.DateField(null=True, blank=True, verbose_name=_("Sailed on"))
    bl_number = models.CharField(max_length=64, blank=True, verbose_name=_("Bill of lading"))
    bl_date = models.DateField(null=True, blank=True, verbose_name=_("B/L date"))
    eta = models.DateField(null=True, blank=True, verbose_name=_("ETA"))
    arrival_port = models.CharField(max_length=64, blank=True, verbose_name=_("Port"))
    arrival_date = models.DateField(null=True, blank=True, verbose_name=_("Arrived on"))
    release_date = models.DateField(null=True, blank=True, verbose_name=_("Customs released on"))
    notification_date = models.DateField(null=True, blank=True, verbose_name=_("Notification (إخطار) date"))
    tracking_url = models.URLField(blank=True, max_length=500, verbose_name=_("Tracking link"))

    # ── delivery and after-sales ────────────────────────────────────────────
    delivery_date = models.DateField(null=True, blank=True, verbose_name=_("Delivered on"))
    delivery_receipt = AttachmentForeignKeyField(
        upload_to='car_import/deals/delivery', allowed_types=['image', 'pdf', 'document'],
        verbose_name=_("Delivery receipt"),
    )
    licensing_state = models.CharField(max_length=64, blank=True, verbose_name=_("Licensing"))
    protection_state = models.CharField(max_length=64, blank=True, verbose_name=_("Protection film"))
    warranty_activated = models.BooleanField(default=False, verbose_name=_("Warranty activated"))

    # ── what the customer sees ──────────────────────────────────────────────
    public_status = models.CharField(max_length=128, blank=True, verbose_name=_("Customer-facing status"))
    public_token = models.CharField(max_length=64, blank=True, db_index=True, verbose_name=_("Tracking token"))
    media_consent = models.BooleanField(
        default=False, verbose_name=_("Consent for photos and video"),
        help_text=_("The customer agreed in the contract that their car may appear in content"),
    )

    class Meta:
        verbose_name = _("Car Deal")
        verbose_name_plural = _("Car Deals")
        ordering = ['-id']
        indexes = [
            models.Index(fields=['state', 'import_stage']),
            models.Index(fields=['partner']),
        ]

    def __str__(self):
        car = str(self.vehicle) if self.vehicle_id else _("no car yet")
        return f"{self.name or '—'} · {car}"

    # ── change detection ────────────────────────────────────────────────────
    #: Set in pre_save, read in post_save. Never cached in __init__: the
    #: serializer defers columns, so a partially loaded instance would report
    #: "no stage" and every save would look like a stage change — and message
    #: the customer about a stage they never entered.
    _stage_changed_from = None
    _stage_did_change = False

    def _stored_stage_id(self):
        """The stage this deal has in the database right now."""
        if not self.pk:
            return None
        return (type(self)._base_manager
                .filter(pk=self.pk)
                .values_list('import_stage_id', flat=True)
                .first())

    @property
    def attribution_summary(self):
        """Where this customer came from, as one line.

        The platform records it on the LEAD — click-to-WhatsApp referrals,
        UTM campaign, Meta ad — and nothing showed it on the deal, which is the
        screen a manager actually has open when they ask "which advert paid for
        this car?". Read through, never copied: the lead stays the source.
        """
        lead = self.lead if self.lead_id else None
        if lead is None:
            return ''
        bits = []
        origin = getattr(lead, 'lead_origin', '') or ''
        if origin:
            bits.append({'ads': 'إعلان', 'organic': 'أورجانيك'}.get(origin, origin))
        for attr in ('utm_source', 'utm_medium', 'utm_campaign', 'meta_campaign', 'meta_ad'):
            value = getattr(lead, attr, None)
            name = getattr(value, 'name', None)
            if name:
                bits.append(str(name))
        first = getattr(lead, 'meta_first_touch_at', None)
        if first:
            bits.append(f'أول نقرة {first:%Y-%m-%d}')
        return ' · '.join(bits)

    @property
    def days_in_stage(self):
        if not self.stage_entered_at:
            return None
        return (timezone.now() - self.stage_entered_at).days

    # ── rules ───────────────────────────────────────────────────────────────
    def _check_approvals(self):
        """Cancellation and a non-standard schedule are management's calls.

        Straight from the client's approval matrix. The rule was written down
        in their process map and enforced nowhere, which meant the matrix
        described a company the software did not implement.
        """
        from .approval import require

        user = getattr(getattr(self, 'env', None), 'user', None)
        stored = type(self)._base_manager.filter(pk=self.pk).values(
            'state', 'financing_type').first() if self.pk else None

        if self.state == 'cancelled' and (stored or {}).get('state') != 'cancelled':
            require('cancellation', self.amount_paid_marked, deal=self,
                    partner=self.partner, field='state',
                    reason=self.cancel_reason or _("Cancelling this deal"), user=user)

        # A programme flagged `requires_management_approval` — commercial
        # import today — asks before the deal exists, not after money moved.
        if not self.pk:
            from .reference_data import ImportProgram
            program = ImportProgram.objects.filter(code=self.program).only(
                'requires_management_approval', 'name').first()
            if program is not None and program.requires_management_approval:
                require('program_approval', None, partner=self.partner, field='program',
                        reason=_("%(customer)s on %(programme)s") % {
                            'customer': getattr(self.partner, 'name', '') or '—',
                            'programme': program.name},
                        user=user)

        if (self.financing_type == 'direct_instalments'
                and (stored or {}).get('financing_type') != 'direct_instalments'):
            require('payment_schedule', self.amount_agreed, deal=self,
                    partner=self.partner, field='financing_type',
                    reason=_("Instalments instead of the standard schedule"), user=user)

    def _check_instalments_allowed(self):
        """Instalments are refused when the customer holds the initiative.

        Enforced from ``pre_save``, not from ``clean``: Django's ``save()``
        never calls ``clean()``, and neither does this platform's write path
        (`modules/base/genie_serializer/write.py`), so the rule sat here doing
        nothing — the form saved the forbidden combination without a word.
        Raised in ``pre_save`` it becomes the HTTP 400 the form shows.
        """
        if (self.financing_type == 'direct_instalments'
                and self.program == 'initiative'
                and self.customer_is_initiative_holder):
            raise ValidationError({
                'financing_type': _(
                    "Instalments are not available when the customer holds the initiative: "
                    "customs clearance is in their name, so the company has no sale lien "
                    "(client, 2026-09-14). Offer a showroom car instead."
                )
            })

    def clean(self):
        super().clean()
        self._check_instalments_allowed()

    def pre_create(self):
        super().pre_create()
        # The person who opens the deal is its agent unless somebody says
        # otherwise. The row-level rule "an agent sees their own deals" reads
        # `assigned_to`; a deal with nobody on it is a deal its author cannot
        # find again.
        user = getattr(getattr(self, 'env', None), 'user', None)
        if self.assigned_to_id is None and getattr(user, 'pk', None):
            self.assigned_to = user

    def pre_save(self):
        super().pre_save()
        self._check_instalments_allowed()
        self._check_approvals()
        if self.amount_agreed is not None and self.amount_paid_marked is not None:
            self.amount_due_marked = max(self.amount_agreed - self.amount_paid_marked, 0)
        stored_stage_id = self._stored_stage_id()
        self._stage_changed_from = stored_stage_id
        self._stage_did_change = bool(self.import_stage_id) and self.import_stage_id != stored_stage_id

        if self._stage_did_change:
            self.stage_entered_at = timezone.now()
            if stored_stage_id:
                self.previous_stage_id = stored_stage_id
            stage = self.import_stage
            if stage and stage.is_final and self.state == 'open':
                self.state = 'done'

    def post_save(self):
        """Log every stage move and let the notifier tell the customer."""
        super().post_save()
        if not self._stage_did_change:
            return

        # Cleared first: a save inside the notifier must not log a second time.
        from_stage_id = self._stage_changed_from
        self._stage_did_change = False
        self._stage_changed_from = None

        from car_import.services.stage_notifier import log_and_notify_stage_change
        log_and_notify_stage_change(
            deal=self,
            from_stage_id=from_stage_id,
            to_stage_id=self.import_stage_id,
        )

    # ── buttons ─────────────────────────────────────────────────────────────

    @action
    def action_move_next_stage(queryset):
        """Advance each deal one stage; the customer is told automatically."""
        from car_import.services.stage_machine import move_to_next

        moved, blocked = 0, []
        for deal in queryset:
            try:
                move_to_next(deal)
                moved += 1
            except ValidationError as exc:
                blocked.append(f"{deal.name}: {'; '.join(exc.messages)}")
        message = _("Moved %(count)d deal(s) to the next stage") % {'count': moved}
        if blocked:
            message += "\n" + "\n".join(blocked)
        return {
            'status': True,
            'open_mode': 'message',
            'message': message,
            'data': {},
            'on_success': {'type': 'refresh'},
        }

    @action
    def action_mark_deposit_received(queryset):
        """Mark the deposit as received. No invoice, no journal entry."""
        return CarDeal._mark_payment(queryset, 'deposit_paid', _("Deposit marked as received on %(count)d deal(s)"))

    @action
    def action_mark_fully_paid(queryset):
        """Mark the deal as fully paid, as recorded by the accountant."""
        return CarDeal._mark_payment(queryset, 'fully_paid', _("Marked %(count)d deal(s) as fully paid"))

    @staticmethod
    def _mark_payment(queryset, state, message):
        count = 0
        for deal in queryset:
            deal.payment_state = state
            deal.payment_marked_at = timezone.now()
            deal.payment_marked_by = getattr(deal.env, 'user', None)
            deal.save()
            count += 1
        return {
            'status': True,
            'open_mode': 'message',
            'message': message % {'count': count},
            'data': {},
            'on_success': {'type': 'refresh'},
        }

    @action
    def action_send_stage_update(queryset):
        """Send the current stage's message again — for a customer who asks."""
        from car_import.services.stage_notifier import deliver
        from car_import.models import StageChangeLog

        sent = 0
        for deal in queryset:
            if not deal.import_stage_id:
                continue
            log = StageChangeLog.objects.create(
                deal=deal, from_stage_id=deal.import_stage_id, to_stage_id=deal.import_stage_id,
                changed_by=getattr(deal.env, 'user', None), reason=str(_("Re-sent by an agent")),
                notification_state='pending',
            )
            deliver(log)
            sent += 1
        return {
            'status': True,
            'open_mode': 'message',
            'message': _("Sent the current stage update to %(count)d customer(s)") % {'count': sent},
            'data': {},
            'on_success': {'type': 'refresh'},
        }

    @action
    def action_toggle_ai(queryset):
        """Hand the customer's conversation to a human, or give it back to the AI."""
        from modules.chat.models import Conversation

        changed = 0
        for deal in queryset:
            conversation = (
                Conversation.objects
                .filter(social_partner=deal.partner)
                .order_by('-last_message_time', '-id')
                .first()
            )
            if conversation is None:
                continue
            conversation.handled_by_ai = not conversation.handled_by_ai
            conversation.save(update_fields=['handled_by_ai'])
            changed += 1
        return {
            'status': True,
            'open_mode': 'message',
            'message': _("Switched the AI on or off for %(count)d conversation(s)") % {'count': changed},
            'data': {},
            'on_success': {'type': 'refresh'},
        }

    @action
    def action_build_document_checklist(queryset):
        """Create the paperwork lines this deal's programme asks for.

        Idempotent: it adds what is missing and never touches a document the
        customer has already sent — the programme gets corrected after the fact
        more often than anyone would like.
        """
        from car_import.services.documents import build_checklist, checklist_status

        added = 0
        for deal in queryset:
            added += len(build_checklist(deal))
        status = checklist_status(queryset[0]) if len(queryset) == 1 else None

        message = _("Added %(count)d document line(s).") % {'count': added}
        if status and status['outstanding']:
            outstanding = ', '.join(row['name'] for row in status['outstanding'])
            message += '\n' + str(_("Still outstanding: %(names)s")) % {'names': outstanding}
        return {
            'status': True,
            'open_mode': 'message',
            'message': message,
            'data': {},
            'on_success': {'type': 'refresh'},
        }

    @action
    def action_set_stage(queryset, form):
        """Jump to any stage, or move back, with a reason — and normally no message.

        Separate from "next stage" on purpose, and the distinction is the whole
        feature: moving a deal back because ops mis-clicked must not tell the
        customer their car has un-shipped. So this sets the stage directly,
        suppressing the customer message unless somebody deliberately asks for
        it, and the reason lands in the change log and the chatter.
        """
        from car_import.models import StageChangeLog

        moved = 0
        for deal in queryset:
            previous_id = deal.import_stage_id
            if previous_id == form.import_stage_id:
                continue
            # `notifications_suppressed` is what post_save reads to decide
            # whether the customer hears about a stage move, so the switch is
            # flipped around the save rather than re-implementing the rule.
            was_suppressed = deal.notifications_suppressed
            deal.notifications_suppressed = was_suppressed or not form.notify_customer
            deal.previous_stage_id = previous_id
            deal.import_stage = form.import_stage
            deal.save()
            deal.notifications_suppressed = was_suppressed
            deal.save(update_fields=['notifications_suppressed'])

            StageChangeLog.objects.filter(
                deal=deal, to_stage_id=form.import_stage_id
            ).order_by('-id').update(reason=form.reason)
            deal.message_post(body=_(
                "Stage set by hand to %(stage)s. Reason: %(reason)s")
                % {'stage': str(form.import_stage), 'reason': form.reason})
            moved += 1

        return {'status': True, 'open_mode': 'message', 'data': {},
                'message': _("Moved %(count)d deal(s)") % {'count': moved}}

    @staticmethod
    def _set_state(queryset, state, only_from=None):
        """Through save(), never queryset.update(): the update path skips
        pre_save, which is where the cancellation approval and the chatter
        tracking live. The Cancel button used to bypass the very rule the
        client wrote for it."""
        done, refused = 0, []
        for deal in queryset:
            if only_from and deal.state != only_from:
                continue
            deal.state = state
            try:
                deal.save()
            except ValidationError as exc:
                refused.append(f"{deal.name}: {'; '.join(exc.messages)}")
                continue
            done += 1
        return done, refused

    @action
    def action_hold(queryset):
        """Pause a deal without losing its stage."""
        count, refused = CarDeal._set_state(queryset, 'on_hold', only_from='open')
        message = _("Put %(count)d deal(s) on hold") % {'count': count}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': True, 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_resume(queryset):
        """Reopen a held deal."""
        count, refused = CarDeal._set_state(queryset, 'open', only_from='on_hold')
        message = _("Reopened %(count)d deal(s)") % {'count': count}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': True, 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    @action
    def action_cancel(queryset):
        """Cancel a deal. Nothing is deleted, and no message goes to the customer.
        Management's approval is asked on the way (the client's rule 4)."""
        count, refused = CarDeal._set_state(queryset, 'cancelled')
        message = _("Cancelled %(count)d deal(s). The customer is told by a person, not by the system.") \
            % {'count': count}
        if refused:
            message += "\n" + "\n".join(refused)
        return {'status': bool(count) or not refused, 'open_mode': 'message', 'message': message,
                'data': {}, 'on_success': {'type': 'refresh'}}

    # ── live reactions on the form ──────────────────────────────────────────
    @onchange('partner')
    def _onchange_partner(self):
        """Pick up the customer's latest lead, and the programme it says."""
        if not self.partner_id or self.lead_id:
            return
        try:
            from modules.crm.models import Lead
            lead = Lead.all_objects.filter(partner_id=self.partner_id).order_by('-id').first()
        except Exception:
            lead = None
        if lead is None:
            return
        self.lead = lead
        program = getattr(lead, 'ka_program', None)
        if program in dict(self.PROGRAM):
            self.program = program

    @onchange('amount_agreed')
    def _onchange_amount_agreed(self):
        return self._due_from_marks()

    @onchange('amount_paid_marked')
    def _onchange_amount_paid(self):
        return self._due_from_marks()

    def _due_from_marks(self):
        if self.amount_agreed is None:
            return None
        paid = self.amount_paid_marked or 0
        return {'value': {'amount_due_marked': float(max(self.amount_agreed - paid, 0))}}

    @onchange('financing_type')
    def _onchange_financing_type(self):
        """The bank only means something on bank financing; the rate and the
        term only on a plan with instalments."""
        if self.financing_type != 'bank':
            self.financing_bank = ''
        if self.financing_type == 'cash':
            self.financing_term_months = None
            self.cheques_received = False
