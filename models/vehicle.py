# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel

#: Options that move a car from the medium tier to the full tier.
#: The client confirmed on 2026-09-14: panorama and sunroof count separately,
#: and **any 3 of 6** options put the car in the full tier. Five are named so
#: far; the sixth is still to be confirmed, hence `has_other_tier_option`.
TIER_OPTION_FIELDS = (
    'has_panorama',
    'has_sunroof',
    'has_memory_seats',
    'has_electric_trunk',
    'has_digital_cluster',
    'has_other_tier_option',
)

#: How many of those options make the car "كاملة".
TIER_FULL_THRESHOLD = 3


class Vehicle(BaseModel):
    """A single physical car — not a catalogue item."""

    CONDITION = [
        ('zero', _("Zero (under 50 km)")),
        ('near_zero', _("كسر زيرو")),
        ('used', _("Used")),
    ]
    TIER = [
        ('medium', _("متوسطة")),
        ('full', _("كاملة")),
    ]
    #: How the supplier invoices. It decides whether the 19 % German VAT can be
    #: reclaimed on export, and therefore which price the quote is built on.
    INVOICE_TYPE = [
        ('gross', _("Gross — VAT shown and recoverable")),
        ('net', _("Net — no recoverable VAT")),
        ('unknown', _("Not known yet")),
    ]

    # ── identity ────────────────────────────────────────────────────────────
    vin = models.CharField(
        max_length=17, blank=True, db_index=True, verbose_name=_("VIN"),
        help_text=_("17 characters, never shortened"),
    )
    make = models.CharField(max_length=64, verbose_name=_("Make"))
    model = models.CharField(max_length=128, verbose_name=_("Model"))
    trim = models.CharField(max_length=128, blank=True, verbose_name=_("Trim"))
    model_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Model year"))
    production_month = models.CharField(max_length=16, blank=True, verbose_name=_("Production month"))

    # ── technical ───────────────────────────────────────────────────────────
    cc = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Engine size (cc)"),
        help_text=_("Exact displacement from the car's papers or VIN — the tax band "
                    "switches at 1600 and 2000 cc, and many \"2.0\" engines are 1999 cc"),
    )
    hp = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Power (hp)"))
    fuel = models.CharField(max_length=32, blank=True, verbose_name=_("Fuel"))
    gearbox = models.CharField(max_length=32, blank=True, verbose_name=_("Gearbox"))
    colour_exterior = models.CharField(max_length=64, blank=True, verbose_name=_("Colour (outside)"))
    colour_interior = models.CharField(max_length=64, blank=True, verbose_name=_("Colour (inside)"))
    mileage_km = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Odometer (km)"))
    condition = models.CharField(max_length=16, choices=CONDITION, default='used', verbose_name=_("Condition"))
    accident_free = models.BooleanField(default=False, verbose_name=_("Accident-free (فابريكة)"))

    # ── origin ──────────────────────────────────────────────────────────────
    country_built = models.CharField(max_length=64, blank=True, verbose_name=_("Built in"))
    built_for_eu = models.BooleanField(default=False, verbose_name=_("Built for the EU market"))
    eur1_eligible = models.BooleanField(default=False, verbose_name=_("EUR 1 eligible"))

    # ── commercial ──────────────────────────────────────────────────────────
    listing_url = models.URLField(blank=True, max_length=500, verbose_name=_("Listing URL"))
    source_site = models.CharField(max_length=64, blank=True, default='mobile.de', verbose_name=_("Source"))
    dealer_name = models.CharField(max_length=128, blank=True, verbose_name=_("Dealer"))
    supplier_invoice_type = models.CharField(
        max_length=16, choices=INVOICE_TYPE, default='unknown', verbose_name=_("Supplier invoice"),
        help_text=_("Gross: the invoice shows VAT and the company reclaims it on export, so the "
                    "quote is built on the net price. Net: the price already carries no reclaimable "
                    "VAT. The client's vendor list (2026-09-15) says which supplier is which"),
    )
    seller_is_dealer = models.BooleanField(
        default=True, verbose_name=_("Sold by a dealer"),
        help_text=_("Private listings are already net of VAT (client, 2026-09-15)"),
    )
    vatable = models.BooleanField(
        default=False, verbose_name=_("VAT recoverable"),
        help_text=_("MwSt. ausweisbar — these listings rank first in a search"),
    )
    price_gross_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                          verbose_name=_("Listed price (EUR)"))
    price_net_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        verbose_name=_("Net of VAT (EUR)"))

    # ── the options that decide the deposit tier ────────────────────────────
    has_panorama = models.BooleanField(default=False, verbose_name=_("Panorama roof"))
    has_sunroof = models.BooleanField(default=False, verbose_name=_("Sunroof"))
    has_memory_seats = models.BooleanField(default=False, verbose_name=_("Memory seats"))
    has_electric_trunk = models.BooleanField(default=False, verbose_name=_("Electric trunk"))
    has_digital_cluster = models.BooleanField(default=False, verbose_name=_("Digital cluster"))
    has_other_tier_option = models.BooleanField(
        default=False, verbose_name=_("Other tier option"),
        help_text=_("The client's rule counts 6 options; five are named so far"),
    )
    tier_override = models.CharField(
        max_length=16, choices=TIER, blank=True, verbose_name=_("Tier override"),
        help_text=_("Set only when the deposit sheet disagrees with the option count"),
    )

    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Vehicle")
        verbose_name_plural = _("Vehicles")
        ordering = ['-id']

    def __str__(self):
        parts = [self.make, self.model, self.trim, str(self.model_year or '')]
        return ' '.join(p for p in parts if p).strip() or (self.vin or '—')

    # ── the client's tier rule ──────────────────────────────────────────────
    @property
    def tier_option_count(self):
        """How many of the six tier-driving options this car has."""
        return sum(1 for f in TIER_OPTION_FIELDS if getattr(self, f, False))

    @property
    def deposit_tier(self):
        """
        'full' when the car carries 3 or more of the six options, else 'medium'
        (client, 2026-09-14). An explicit override always wins.
        """
        if self.tier_override:
            return self.tier_override
        return 'full' if self.tier_option_count >= TIER_FULL_THRESHOLD else 'medium'
