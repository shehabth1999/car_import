# -*- coding: utf-8 -*-
"""The expatriate initiative, as an object rather than a word on a contact.

Until now "initiative" was a text field on the customer, which is enough to say
*that* someone has one and nothing else. The business needs more than that:

* a deposit is paid in USD and **refunded after five years** — somebody has to
  know when;
* a holder may modify their application **once**, and once only;
* a holder who will not use it can **sell the right**, which is a market the
  company wants to match buyers into (agent A7 in the plan);
* the deposit's size depends on the car's tier and whether it is bought inside
  or outside Europe, which is what the workbook's 304 rows are for.

Registration for new participants closed in 2024. That is deliberately NOT
enforced here as a hard block: existing holders still transact every day, and
the module's job is to record what is, not to argue with it.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel


class Initiative(BaseModel):
    """One holder's participation in the expatriate car initiative."""

    TYPE = [
        ('gulf', _("Gulf")),
        ('european', _("European")),
        ('other', _("Other")),
    ]
    STATUS = [
        ('none', _("Not applied")),
        ('applied', _("Applied")),
        ('issued', _("Issued")),
        ('modified', _("Modified")),
        ('used', _("Used")),
        ('expired', _("Expired")),
        ('for_sale', _("Offered for sale")),
        ('sold', _("Sold")),
    ]
    TIER = [('medium', _("Medium")), ('full', _("Full"))]

    holder = models.ForeignKey('base.Partner', on_delete=models.PROTECT,
                               related_name='car_import_initiatives',
                               verbose_name=_("Holder"))
    country = models.CharField(max_length=64, blank=True, verbose_name=_("Country"))
    initiative_type = models.CharField(max_length=16, choices=TYPE, default='gulf',
                                       verbose_name=_("Type"))
    approval_number = models.CharField(max_length=64, blank=True, db_index=True,
                                       verbose_name=_("Approval number"))
    status = models.CharField(max_length=16, choices=STATUS, default='none',
                              verbose_name=_("Status"))

    # ── the deposit ─────────────────────────────────────────────────────────
    deposit_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                      verbose_name=_("Deposit (USD)"))
    tier = models.CharField(max_length=16, choices=TIER, blank=True, verbose_name=_("Tier"))
    deposit_paid_on = models.DateField(null=True, blank=True, verbose_name=_("Deposit paid on"))
    refund_due_on = models.DateField(null=True, blank=True, verbose_name=_("Refund due on"),
                                     help_text=_("Five years after the deposit was paid"))
    refunded_on = models.DateField(null=True, blank=True, verbose_name=_("Refunded on"))

    # ── the one modification ────────────────────────────────────────────────
    modifications_used = models.PositiveIntegerField(
        default=0, verbose_name=_("Modifications used"),
        help_text=_("One is the maximum. The second request is refused."))

    # ── the car it is attached to ───────────────────────────────────────────
    deal = models.ForeignKey('car_import.CarDeal', null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='initiatives', verbose_name=_("Used on deal"))

    # ── selling the right ───────────────────────────────────────────────────
    transferable = models.BooleanField(default=False, verbose_name=_("May be transferred"))
    asking_price_egp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                           verbose_name=_("Asking price (EGP)"))
    participation_split = models.CharField(max_length=190, blank=True,
                                           verbose_name=_("Participation split"))
    buyer = models.ForeignKey('base.Partner', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='car_import_bought_initiatives',
                              verbose_name=_("Buyer"))

    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Initiative")
        verbose_name_plural = _("Initiatives")
        ordering = ['-id']
        indexes = [
            models.Index(fields=['status', 'transferable']),
            models.Index(fields=['refund_due_on']),
        ]

    def __str__(self):
        who = getattr(self.holder, 'name', '') or '—'
        return f'{who} · {self.get_initiative_type_display()} · {self.get_status_display()}'

    @property
    def modification_available(self):
        """False once the single allowed modification has been used."""
        return self.modifications_used < 1

    @property
    def for_sale(self):
        return self.status == 'for_sale' and self.transferable

    def pre_save(self):
        super().pre_save()
        # The refund date is arithmetic, not data entry: five years to the day
        # from the deposit. Computed here so nobody has to remember, and so a
        # corrected payment date corrects the refund date with it.
        if self.deposit_paid_on and not self.refunded_on:
            try:
                self.refund_due_on = self.deposit_paid_on.replace(
                    year=self.deposit_paid_on.year + 5)
            except ValueError:            # 29 February
                self.refund_due_on = self.deposit_paid_on.replace(
                    year=self.deposit_paid_on.year + 5, day=28)
