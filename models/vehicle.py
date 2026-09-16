# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.fields import AttachmentForeignKeyField, AttachmentManyToManyField
from modules.base.models.base import BaseModel

#: Options that move a car from the medium tier to the full tier.
#: The client confirmed on 2026-09-14: panorama and sunroof count separately,
#: and **any 3 of 6** options put the car in the full tier. All six were
#: confirmed by the owner on 2026-09-16, in his own words:
#:   فتحة سقف · سقف بانوراما · شنطة كهرباء · كراسي كهرباء · كراسي جلد · عداد ديجيتال
#:
#: Two corrections came with that list. What was recorded as "memory seats" is
#: ELECTRIC seats — a different option, and a commoner one. And leather seats,
#: which had been missed entirely, take the sixth slot that was a placeholder.
#: Both mattered: the count decides the tier, the tier decides the deposit, and
#: the deposit is thousands of dollars.
TIER_OPTION_FIELDS = (
    'has_sunroof',
    'has_panorama',
    'has_electric_trunk',
    'has_electric_seats',
    'has_leather_seats',
    'has_digital_cluster',
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

    BODY = [
        ('sedan', _("Saloon")),
        ('suv', _("SUV")),
        ('coupe', _("Coupé")),
        ('hatchback', _("Hatchback")),
        ('estate', _("Estate")),
        ('convertible', _("Convertible")),
        ('van', _("Van")),
    ]

    # ── identity ────────────────────────────────────────────────────────────
    vin = models.CharField(
        max_length=17, blank=True, db_index=True, verbose_name=_("VIN"),
        help_text=_("17 characters, never shortened"),
    )
    #: The German order reference. It is printed on the contract — clause 2 asks
    #: for "كونفيجريشن رقم" — and on a factory order it is the only identifier
    #: that exists before a VIN does. It belongs to the car, not to the piece of
    #: paper: the same number has to appear on the contract, the annex and the
    #: supplier's confirmation, and they have to agree.
    configuration_number = models.CharField(
        max_length=64, blank=True, db_index=True, verbose_name=_("Configuration number"),
        help_text=_("The supplier's order reference, printed on the contract"),
    )
    internal_reference = models.CharField(max_length=64, blank=True,
                                          verbose_name=_("Internal reference"))
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
    has_electric_trunk = models.BooleanField(default=False, verbose_name=_("Electric boot (شنطة كهرباء)"))
    has_electric_seats = models.BooleanField(default=False, verbose_name=_("Electric seats (كراسي كهرباء)"))
    has_leather_seats = models.BooleanField(default=False, verbose_name=_("Leather seats (كراسي جلد)"))
    has_digital_cluster = models.BooleanField(default=False, verbose_name=_("Digital cluster (عداد ديجيتال)"))
    tier_override = models.CharField(
        max_length=16, choices=TIER, blank=True, verbose_name=_("Tier override"),
        help_text=_("Set only when the deposit sheet disagrees with the option count"),
    )

    # ── specification, as the annex prints it ───────────────────────────────
    body = models.CharField(max_length=16, choices=BODY, blank=True, verbose_name=_("Body"))
    upholstery = models.CharField(max_length=64, blank=True, verbose_name=_("Upholstery"))
    euro_norm = models.CharField(max_length=16, blank=True, verbose_name=_("EURO norm"))
    built_for_market = models.CharField(
        max_length=64, blank=True, verbose_name=_("Built for market"),
        help_text=_("Not the same as where it was built — EUR 1 turns on this one"),
    )
    export_port = models.CharField(max_length=64, blank=True, verbose_name=_("Export port"))
    inspection_report = models.TextField(blank=True, verbose_name=_("Inspection report"))
    negotiated_discount_eur = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name=_("Negotiated discount (EUR)"),
        help_text=_("What was talked off the advertised price. Cost data — the "
                    "sales agents do not see it"),
    )

    # ── media ───────────────────────────────────────────────────────────────
    # Stage 6 sends the customer photos and a walk-around video from the Berlin
    # showroom. Until now the stage could send media and the car had nowhere to
    # keep it, so the only copy lived in a WhatsApp thread.
    photos = AttachmentManyToManyField(
        upload_to='car_import/vehicles/photos', allowed_types=['image'],
        verbose_name=_("Photos"), blank=True,
    )
    walkaround_video = AttachmentForeignKeyField(
        upload_to='car_import/vehicles/video', allowed_types=['video'],
        verbose_name=_("Walk-around video"),
    )
    car_card = AttachmentForeignKeyField(
        upload_to='car_import/vehicles/cards', allowed_types=['pdf', 'image', 'document'],
        verbose_name=_("Car card"),
    )
    vin_option_list = AttachmentForeignKeyField(
        upload_to='car_import/vehicles/options', allowed_types=['pdf', 'document', 'image'],
        verbose_name=_("VIN option list"),
        help_text=_("The factory list the supplier sends against the VIN"),
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
