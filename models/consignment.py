# -*- coding: utf-8 -*-
"""L6 — consignment brokerage (عقد وساطة تجارية حصري).

The sixth revenue line, and the only one of the six with no software at all
until now. The company takes an exclusive written mandate to sell somebody
else's car inside an agreed price band and earns a percentage of what it
finally sells for.

Four terms out of their own brokerage contract decide whether a commission is
owed, and all four are dates or flags rather than opinions — which is exactly
why they belong in a row:

* **exclusivity** — while the mandate runs, the owner may not sell it
  themselves;
* **auto-renewal** — it rolls over unless somebody stops it;
* **a 90-day tail** — a buyer the company introduced who signs after the
  mandate ends still owes commission. Without a recorded introduction date this
  is unarguable in either direction;
* **a 7-day cure period** before a breach counts.

The commission percentage is **blank in the client's own template**. It is a
field here with no default: the one number this module will not invent.

Money, as everywhere else in this system, is a mark and not accounting. This
records what was agreed and what became due. It raises no invoice.
"""
from datetime import timedelta
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


class ConsignmentMandate(SequenceMixin, BaseModel, BranchMixin, FullChatterMixin):
    """One exclusive mandate to sell one owner's car."""

    sequence_code = 'car_import.consignment'

    objects = BranchAwareManager()
    all_objects = models.Manager()

    _mail_track = {'state': None, 'sold_price_egp': None}

    STATE = [
        ('draft', _("Draft")),
        ('active', _("Active")),
        ('reserved', _("Deposit taken")),
        ('sold', _("Sold")),
        ('expired', _("Expired")),
        ('withdrawn', _("Withdrawn")),
    ]

    name = models.CharField(max_length=32, blank=True, verbose_name=_("Reference"))
    state = models.CharField(max_length=16, choices=STATE, default='draft',
                             verbose_name=_("Status"))
    owner = models.ForeignKey('base.Partner', on_delete=models.PROTECT,
                              related_name='consignment_mandates', verbose_name=_("Owner"))
    vehicle = models.ForeignKey('car_import.Vehicle', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='consignments',
                                verbose_name=_("Car"))
    car_description = models.CharField(
        max_length=190, blank=True, verbose_name=_("Car"),
        help_text=_("When the car is not one of ours — most of them are not"))
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+',
                                    verbose_name=_("Broker"))

    # ── the mandate ─────────────────────────────────────────────────────────
    signed_on = models.DateField(null=True, blank=True, verbose_name=_("Signed on"))
    expires_on = models.DateField(null=True, blank=True, verbose_name=_("Runs until"))
    is_exclusive = models.BooleanField(default=True, verbose_name=_("Exclusive"))
    auto_renews = models.BooleanField(default=True, verbose_name=_("Renews automatically"))
    tail_days = models.PositiveIntegerField(
        default=90, verbose_name=_("Tail (days)"),
        help_text=_("A buyer we introduced who signs within this many days after "
                    "the mandate ends still owes commission"))
    cure_days = models.PositiveIntegerField(default=7, verbose_name=_("Cure period (days)"))

    price_floor_egp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                          verbose_name=_("Price band — from (EGP)"))
    price_ceiling_egp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                            verbose_name=_("Price band — to (EGP)"))
    #: No default, deliberately. It is blank in the client's own template, and
    #: a plausible guess here would be a number somebody quotes to an owner.
    commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name=_("Commission %"),
        help_text=_("Of the final price. Blank in the client's template — ask before quoting"))
    commission_fixed_egp = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name=_("Commission — fixed instead (EGP)"))
    marketing_cost_note = models.CharField(
        max_length=255, blank=True, verbose_name=_("Marketing costs"),
        help_text=_("Borne by the broker; anything extraordinary needs the owner "
                    "in writing"))

    # ── what happened ───────────────────────────────────────────────────────
    buyer = models.ForeignKey('base.Partner', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='consignment_purchases', verbose_name=_("Buyer"))
    buyer_introduced_on = models.DateField(
        null=True, blank=True, verbose_name=_("Buyer introduced on"),
        help_text=_("The date that decides whether the tail applies"))
    deposit_taken_egp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                            verbose_name=_("Deposit taken as agent (EGP)"))
    sold_on = models.DateField(null=True, blank=True, verbose_name=_("Sold on"))
    sold_price_egp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                         verbose_name=_("Sold for (EGP)"))
    commission_due_egp = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                             verbose_name=_("Commission due (EGP)"),
                                             editable=False)
    commission_paid = models.BooleanField(default=False, verbose_name=_("Commission received"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Consignment mandate")
        verbose_name_plural = _("Consignment mandates")
        ordering = ['-id']
        indexes = [models.Index(fields=['state', 'expires_on'])]

    def __str__(self):
        car = str(self.vehicle) if self.vehicle_id else (self.car_description or '—')
        return f'{self.name or "—"} · {car}'

    # ── the rules that decide money ─────────────────────────────────────────
    @property
    def tail_ends_on(self):
        """The last day a previously introduced buyer still owes commission."""
        if not self.expires_on:
            return None
        return self.expires_on + timedelta(days=self.tail_days or 0)

    @property
    def commission_is_owed(self):
        """True when this sale falls inside the mandate, or inside its tail.

        The tail only bites for a buyer the company introduced, and only when
        the introduction is on record. An undated introduction is not evidence
        of anything, so it counts as no claim rather than as a claim we cannot
        prove.
        """
        if not self.sold_on:
            return False
        if self.expires_on is None or self.sold_on <= self.expires_on:
            return True
        tail_end = self.tail_ends_on
        return bool(self.buyer_introduced_on
                    and self.buyer_introduced_on <= self.expires_on
                    and tail_end and self.sold_on <= tail_end)

    def compute_commission(self):
        if not self.commission_is_owed:
            return 0
        if self.commission_fixed_egp:
            return self.commission_fixed_egp
        if self.commission_pct and self.sold_price_egp:
            return (self.sold_price_egp * self.commission_pct / 100).quantize(Decimal('0.01'))
        return 0

    def pre_save(self):
        super().pre_save()
        if (self.price_floor_egp and self.price_ceiling_egp
                and self.price_floor_egp > self.price_ceiling_egp):
            raise ValidationError({'price_ceiling_egp': _(
                "The price band runs backwards.")})
        # A sale below the band the owner agreed is the company selling their
        # car for less than they permitted. It is not ours to wave through.
        if (self.sold_price_egp and self.price_floor_egp
                and self.sold_price_egp < self.price_floor_egp):
            from .approval import require
            require('car_discount', self.price_floor_egp - self.sold_price_egp,
                    partner=self.owner, field='sold_price_egp',
                    reason=_("Selling below the agreed price band"),
                    user=getattr(getattr(self, 'env', None), 'user', None))
        self.commission_due_egp = self.compute_commission()

    @action
    def action_mark_sold(queryset):
        """Close the mandate and work out what is owed."""
        done = 0
        for mandate in queryset:
            if not mandate.sold_price_egp:
                continue
            mandate.state = 'sold'
            mandate.sold_on = mandate.sold_on or timezone.localdate()
            mandate.save()
            done += 1
        return {'status': bool(done), 'open_mode': 'message',
                'message': _("Closed %(count)d mandate(s)") % {'count': done},
                'data': {}, 'on_success': {'type': 'refresh'}}
