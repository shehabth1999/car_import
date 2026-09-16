# -*- coding: utf-8 -*-
"""The company's price calculator, as data.

Taken from the client's own workbook (`New Quotation.xlsx`, received
2026-09-16), cell by cell, and turned into rows management can edit — because
the owner said in the same message that *"الاسعار دي قابلة للتعديل على حسب حاجة
السوق"*. A calculator that needs a developer to change a percentage is not a
calculator that survives a market.

The workbook's own logic, for the record:

    net    = gross / 1.19
    admin  = banded on GROSS, computed on NET
    total  = net + shipping + admin + EUR 1 + shipping-type
    deposit = total × a percentage, also banded on GROSS

Two things about those bands are worth stating out loud, because they look like
mistakes and are not:

* the cheapest band's admin fee is **−750**, a discount, not a charge;
* the deposit percentage is **not monotonic** — 15 %, then 25 %, 25 %, then back
  to 15 % and 15 %. A 47,000 € car asks for a bigger share up front than an
  89,000 € one. That is what the sheet says, so that is what this does.
"""
from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel

from .reference_data import EffectiveMixin


class PricingBand(BaseModel, EffectiveMixin):
    """One price bracket: what it costs to handle, and what to pay up front."""

    ADMIN_FEE_TYPE = [
        ('fixed', _("A fixed amount")),
        ('percent_of_net', _("A percentage of the net price")),
    ]

    name = models.CharField(max_length=120, verbose_name=_("Band"))
    sequence = models.PositiveIntegerField(default=10, verbose_name=_("Order"))

    # Bounds are on the GROSS price — the number the German advert shows and the
    # only one an agent types in.
    gross_from_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                         verbose_name=_("From (gross EUR)"))
    gross_to_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                       verbose_name=_("To (gross EUR)"),
                                       help_text=_("Leave empty for the top band"))

    admin_fee_type = models.CharField(max_length=20, choices=ADMIN_FEE_TYPE,
                                      default='percent_of_net', verbose_name=_("Admin fee is"))
    admin_fee_value = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                          verbose_name=_("Admin fee value"),
                                          help_text=_("An amount, or a percentage — a negative "
                                                      "amount is a discount, which the cheapest "
                                                      "band actually uses"))
    deposit_pct = models.DecimalField(max_digits=5, decimal_places=2, default=15,
                                      verbose_name=_("Deposit %"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Pricing band")
        verbose_name_plural = _("Pricing bands")
        ordering = ['sequence', 'gross_from_eur']

    def __str__(self):
        ceiling = f'{self.gross_to_eur:,.0f}' if self.gross_to_eur is not None else '∞'
        return f'{self.gross_from_eur:,.0f} – {ceiling} €'

    def admin_fee_for(self, net_eur):
        """What this band charges to handle a car at that net price."""
        if self.admin_fee_type == 'fixed':
            return Decimal(self.admin_fee_value)
        return (Decimal(net_eur) * Decimal(self.admin_fee_value) / Decimal(100)).quantize(
            Decimal('0.01'))

    @classmethod
    def for_gross(cls, gross_eur, on=None):
        """The band a price falls into, or None.

        None is a real answer: the workbook returns "الرجاء إدخال سعر صحيح" for a
        price outside every band, and a calculator that silently picks the
        nearest band would quote a wrong deposit with total confidence.
        """
        value = Decimal(gross_eur)
        for band in cls.in_force(on=on).order_by('sequence', 'gross_from_eur'):
            if value < Decimal(band.gross_from_eur):
                continue
            if band.gross_to_eur is not None and value > Decimal(band.gross_to_eur):
                continue
            return band
        return None
