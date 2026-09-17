# -*- coding: utf-8 -*-
"""Which decisions a sales agent is not allowed to make.

The client's own process map lists nine of them, and the column heading is
blunt: *"Never decided by an agent or the AI"*. Until now the rules lived in
that document and nowhere in the software — the quotation screen would take any
discount an agent typed, from any agent, with no ceiling and no record.

Two objects, because they answer two different questions:

* **`ApprovalPolicy`** — the rule. Subject, threshold, who approves. Management
  edits it, the way they edit a fee or a pricing band, because a threshold that
  needs a developer is a threshold that gets worked around.
* **`ApprovalRequest`** — one decision, asked and answered. It exists so that
  "management approved it" is a row with a name and a timestamp rather than a
  sentence somebody remembers.

The design rule everywhere here: **a request blocks, it does not warn.** A
warning on a screen is a warning a busy agent clicks past, and the thing on the
other side of these particular rules is the company's margin.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.base.decorators import action
from modules.base.models.base import BaseModel
from modules.notifications.models.mixins import FullChatterMixin

from .reference_data import EffectiveMixin

#: The subjects the client named. Codes are stable; the wording and the numbers
#: are theirs to change.
SUBJECT = [
    ('car_discount', _("Discount on the car's price")),
    ('fee_discount', _("Discount on the company's fees")),
    ('payment_schedule', _("A payment schedule other than the standard")),
    ('cancellation', _("Cancellation, refund or settlement")),
    ('fx_rate', _("The transfer rate and its commission")),
    ('bank_details', _("Giving out bank account details")),
    ('complaint', _("A complaint about condition, a missing option or damage")),
    ('sourcing_outside_eu', _("Sourcing outside Germany or the EU")),
    ('contract_signature', _("Signing the contract")),
    ('program_approval', _("Opening a deal on a programme that needs management")),
    # A consignment sale below the band the owner agreed. Its own subject:
    # the figures are EGP, and `car_discount` carries a EUR threshold.
    ('consignment_below_band', _("Selling a consigned car below the agreed price band")),
]


class ApprovalPolicy(BaseModel, EffectiveMixin):
    """One rule: over this amount, on this subject, somebody else decides."""

    subject = models.CharField(max_length=32, choices=SUBJECT, verbose_name=_("Subject"))
    name = models.CharField(max_length=190, blank=True, verbose_name=_("Rule"))
    #: Null means "always", which is how the client worded most of them: *any*
    #: discount on the company fees, *any* non-standard schedule. A threshold of
    #: zero would mean the same thing and read as an oversight.
    threshold_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name=_("Needs approval above"),
        help_text=_("Leave empty when the subject always needs approval"))
    currency = models.CharField(max_length=8, blank=True, default='EUR',
                                verbose_name=_("Currency"))
    approver_group = models.CharField(
        max_length=64, default='car_import.management', verbose_name=_("Approved by"),
        help_text=_("A group's technical name, e.g. car_import.management"))
    is_active = models.BooleanField(default=True, verbose_name=_("In force"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Approval rule")
        verbose_name_plural = _("Approval rules")
        ordering = ['subject']

    def __str__(self):
        if self.threshold_amount is None:
            return f'{self.get_subject_display()} — {_("always")}'
        return f'{self.get_subject_display()} > {self.threshold_amount:,.0f} {self.currency}'

    def covers(self, amount=None):
        """True when this rule bites for that amount."""
        if not self.is_active:
            return False
        if self.threshold_amount is None:
            return True
        return Decimal(amount or 0) > Decimal(self.threshold_amount)

    @classmethod
    def for_subject(cls, subject, on=None):
        return cls.in_force(on=on, subject=subject, is_active=True).first()


class ApprovalRequest(BaseModel, FullChatterMixin):
    """One decision, asked and answered, with a name on it."""

    STATE = [
        ('pending', _("Waiting")),
        ('approved', _("Approved")),
        ('refused', _("Refused")),
    ]

    subject = models.CharField(max_length=32, choices=SUBJECT, verbose_name=_("Subject"))
    policy = models.ForeignKey(ApprovalPolicy, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='requests', verbose_name=_("Rule"))
    state = models.CharField(max_length=16, choices=STATE, default='pending',
                             verbose_name=_("Status"))

    deal = models.ForeignKey('car_import.CarDeal', null=True, blank=True,
                             on_delete=models.CASCADE, related_name='approval_requests',
                             verbose_name=_("Deal"))
    quote = models.ForeignKey('car_import.Quote', null=True, blank=True,
                              on_delete=models.CASCADE, related_name='approval_requests',
                              verbose_name=_("Quotation"))
    partner = models.ForeignKey('base.Partner', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='car_approval_requests', verbose_name=_("Customer"))

    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                 verbose_name=_("Amount"))
    currency = models.CharField(max_length=8, blank=True, default='EUR', verbose_name=_("Currency"))
    reason = models.TextField(blank=True, verbose_name=_("Why"))

    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+',
                                     verbose_name=_("Asked by"))
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+',
                                   verbose_name=_("Decided by"), editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Decided at"),
                                      editable=False)
    decision_note = models.CharField(max_length=255, blank=True, verbose_name=_("Note"))

    class Meta:
        verbose_name = _("Approval request")
        verbose_name_plural = _("Approval requests")
        ordering = ['-id']
        indexes = [models.Index(fields=['state', 'subject'])]

    def __str__(self):
        return f'{self.get_subject_display()} · {self.get_state_display()}'

    def post_create(self):
        super().post_create()
        self._tell_the_approvers()

    def _tell_the_approvers(self):
        """Ask the people who can actually say yes, where they can say it."""
        from car_import.services import internal_note
        from car_import.tasks import _users_in_groups

        group = (self.policy.approver_group if self.policy_id
                 else 'car_import.management')
        approvers = _users_in_groups([group])
        if not approvers:
            return

        amount = (f'{self.amount:,.2f} {self.currency}' if self.amount is not None else '—')
        body = (f'🔐 مطلوب موافقة — {self.get_subject_display()}\n'
                f'المبلغ: {amount}\n'
                f'السبب: {self.reason or "—"}\n'
                'الموافقة من شاشة «طلبات الموافقة».')

        conversation = _conversation_for(self.partner)
        if conversation is not None:
            internal_note.post(conversation, body, recipients=approvers,
                               subject='مطلوب موافقة الإدارة')
            return
        _notify(approvers, 'مطلوب موافقة الإدارة', body)

    # ── the decision ────────────────────────────────────────────────────────
    @action
    def action_approve(queryset):
        return _decide(queryset, 'approved', _("Approved %(count)d request(s)"))

    @action
    def action_refuse(queryset):
        return _decide(queryset, 'refused', _("Refused %(count)d request(s)"))


def _decide(queryset, state, template):
    done = 0
    for request in queryset:
        if request.state != 'pending':
            continue
        request.state = state
        request.decided_at = timezone.now()
        request.decided_by = getattr(getattr(request, 'env', None), 'user', None)
        request.save()
        _tell_the_requester(request)
        done += 1
    return {'status': bool(done), 'open_mode': 'message',
            'message': template % {'count': done}, 'data': {},
            'on_success': {'type': 'refresh'}}


def _tell_the_requester(request):
    """The agent who asked hears the answer where they asked — the thread —
    and in their inbox. Until now a decision was a row nobody was told about,
    and the agent found out by trying the save again."""
    user = request.requested_by
    if user is None:
        return
    verdict = 'تمت الموافقة ✅' if request.state == 'approved' else 'مرفوض ❌'
    amount = (f'{request.amount:,.2f} {request.currency}' if request.amount is not None else '—')
    who = getattr(request.decided_by, 'name', None) or getattr(request.decided_by, 'email', '') or ''
    body = (f'{verdict} — {request.get_subject_display()}\n'
            f'المبلغ: {amount}\n'
            f'القرار: {who}' + (f'\nملاحظة: {request.decision_note}' if request.decision_note else '')
            + ('\nممكن تحفظ التعديل دلوقتي.' if request.state == 'approved' else ''))
    conversation = _conversation_for(request.partner)
    if conversation is not None:
        try:
            from car_import.services import internal_note
            internal_note.post(conversation, body, recipients=[user], subject='قرار الإدارة')
            return
        except Exception:
            pass
    _notify([user], 'قرار الإدارة', body)


def _conversation_for(partner):
    if partner is None:
        return None
    try:
        from modules.chat.models import Conversation
        return (Conversation.objects.filter(social_partner=partner)
                .order_by('-last_message_time', '-id').first())
    except Exception:
        return None


def _notify(users, subject, body):
    partner_ids = [u.partner_id for u in users if getattr(u, 'partner_id', None)]
    if not partner_ids:
        return
    try:
        from modules.notifications.services.post_notification import post_notification
        post_notification(partner_ids=partner_ids, subject=subject, body=body,
                          url='/genie/', category='car_import')
    except Exception:
        pass


# ── the guard the screens call ─────────────────────────────────────────────
def require(subject, amount=None, *, deal=None, quote=None, partner=None,
            reason='', field=None, user=None):
    """Raise unless this decision is allowed, or has already been approved.

    Blocking, not warning. A warning is something a busy agent clicks past, and
    what sits on the other side of these rules is the company's margin.

    Calling it again after approval is safe: an approved request for the same
    subject and the same amount lets the save through, which is what makes
    "ask, get approved, save" work as a workflow rather than a dead end.
    """
    policy = ApprovalPolicy.for_subject(subject)
    if policy is None or not policy.covers(amount):
        return None

    # Match on whatever links the request has. A quotation being CREATED
    # has no pk yet, so its request is filed with quote=None and the partner;
    # matching on `quote=self` afterwards found nothing, and every later save
    # of that quotation raised a fresh request — the discount could never be
    # saved twice.
    from django.db.models import Q
    link = Q()
    if deal is not None and getattr(deal, 'pk', None):
        link |= Q(deal=deal)
    if quote is not None and getattr(quote, 'pk', None):
        link |= Q(quote=quote)
    if partner is not None and getattr(partner, 'pk', None):
        link |= Q(partner=partner, quote__isnull=True)
    if not link:
        link = Q(deal__isnull=True, quote__isnull=True, partner__isnull=True)
    scope = ApprovalRequest.objects.filter(link, subject=subject)

    existing = scope.filter(state='approved').order_by('-id').first()
    if existing is not None and (existing.amount or 0) >= Decimal(amount or 0):
        return existing

    pending = scope.filter(state='pending').order_by('-id').first()
    if pending is None:
        pending = ApprovalRequest.objects.create(
            subject=subject, policy=policy, deal=deal, quote=quote, partner=partner,
            amount=amount, currency=policy.currency or 'EUR', reason=reason,
            requested_by=user)

    message = _(
        "This needs management's approval: %(rule)s. Request #%(id)s has been "
        "sent and is waiting — the change is not saved until it is approved."
    ) % {'rule': str(policy), 'id': pending.pk}
    raise ValidationError({field: message} if field else message)
