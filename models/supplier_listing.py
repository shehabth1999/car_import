# -*- coding: utf-8 -*-
"""A car offered for sale on a supplier marketplace — today, mobile.de.

A snapshot, not a live view. Cars sell fast, and the most common embarrassment
in the client's own chat history is quoting one that is already gone
("اتباعت"), so every row records when it was last seen and whether it still
exists. A nightly refresh flips `still_available` before the customer finds out.

The commercially important column is `vatable`. The whole price stack starts
from the price NET of the 19 % German VAT, and that reclaim only exists on a car
sold with VAT shown separately. Quoting a non-vatable car at a net price
understates it by roughly the VAT — a five-figure error per deal.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel


class SupplierListing(BaseModel):
    """One advert, as it looked the last time we read it."""

    SOURCE = [
        ('mobile.de', 'mobile.de'),
        ('autoscout24', 'AutoScout24'),
        ('manual', _("Entered by hand")),
    ]
    SELLER_TYPE = [
        ('dealer', _("Dealer")),
        ('private', _("Private seller")),
        ('unknown', _("Unknown")),
    ]

    # ── identity ────────────────────────────────────────────────────────────
    source = models.CharField(max_length=32, choices=SOURCE, default='mobile.de',
                              verbose_name=_("Source"))
    ad_id = models.CharField(max_length=64, db_index=True, verbose_name=_("Advert number"))
    url = models.URLField(max_length=500, blank=True, verbose_name=_("Advert link"))

    # ── the car ─────────────────────────────────────────────────────────────
    make = models.CharField(max_length=64, blank=True, verbose_name=_("Make"))
    model = models.CharField(max_length=128, blank=True, verbose_name=_("Model"))
    version = models.CharField(max_length=190, blank=True, verbose_name=_("Version"))
    model_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Model year"))
    first_registration = models.CharField(max_length=16, blank=True,
                                          verbose_name=_("First registration"))
    mileage_km = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Odometer (km)"))
    cc = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Engine (cc)"))
    power_kw = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Power (kW)"))
    power_hp = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Power (hp)"))
    fuel = models.CharField(max_length=32, blank=True, verbose_name=_("Fuel"))
    gearbox = models.CharField(max_length=32, blank=True, verbose_name=_("Gearbox"))
    colour_exterior = models.CharField(max_length=64, blank=True, verbose_name=_("Colour"))
    condition_new = models.BooleanField(default=False, verbose_name=_("Brand new"))
    accident_free = models.BooleanField(default=False, verbose_name=_("Accident-free"))

    # ── the money ───────────────────────────────────────────────────────────
    price_gross_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                          verbose_name=_("Listed price (EUR)"))
    vatable = models.BooleanField(
        default=False, verbose_name=_("VAT deductible"),
        help_text=_("MwSt. ausweisbar — the 19% is reclaimable on export. "
                    "The price stack is only net when this is true."),
    )
    vat_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=19,
                                       verbose_name=_("German VAT %"))

    # ── who is selling ──────────────────────────────────────────────────────
    seller_name = models.CharField(max_length=190, blank=True, verbose_name=_("Seller"))
    seller_type = models.CharField(max_length=16, choices=SELLER_TYPE, default='unknown',
                                   verbose_name=_("Seller type"))
    seller_city = models.CharField(max_length=128, blank=True, verbose_name=_("City"))
    country = models.CharField(max_length=8, blank=True, verbose_name=_("Country"))

    # ── the snapshot ────────────────────────────────────────────────────────
    images = models.JSONField(default=list, blank=True, verbose_name=_("Photos"))
    features = models.JSONField(default=list, blank=True, verbose_name=_("Options"))
    raw = models.JSONField(default=dict, blank=True, verbose_name=_("Raw response"))
    first_seen_at = models.DateTimeField(null=True, blank=True, verbose_name=_("First seen"))
    last_seen_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last seen"))
    still_available = models.BooleanField(default=True, verbose_name=_("Still listed"))
    gone_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Gone since"))

    # ── provenance — never let a fake look real ─────────────────────────────
    is_simulated = models.BooleanField(
        default=False, verbose_name=_("Simulated"),
        help_text=_("Came from the built-in simulator, not from mobile.de. "
                    "Never quote a simulated car to a customer."),
    )

    # ── links into our own world ────────────────────────────────────────────
    vehicle = models.ForeignKey('car_import.Vehicle', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='listings',
                                verbose_name=_("Car record"))
    deal = models.ForeignKey('car_import.CarDeal', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='candidate_listings',
                             verbose_name=_("Deal"))

    class Meta:
        verbose_name = _("Supplier listing")
        verbose_name_plural = _("Supplier listings")
        ordering = ['-last_seen_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['source', 'ad_id'], name='uniq_listing_per_source'),
        ]
        indexes = [
            models.Index(fields=['make', 'model', 'model_year']),
            models.Index(fields=['still_available', 'vatable']),
        ]

    def __str__(self):
        bits = [self.make, self.model, self.version or '', str(self.model_year or '')]
        label = ' '.join(b for b in bits if b).strip() or self.ad_id
        return f"{label} — {self.price_gross_eur or '?'} €"

    # ── the one calculation that belongs here ───────────────────────────────
    @property
    def price_net_eur(self):
        """The cost the price stack starts from.

        Only a vatable car has a net price: on anything else the listed price IS
        the cost, because there is no reclaim. Returning the gross price for a
        non-vatable car is deliberate — it is the honest number.
        """
        if self.price_gross_eur is None:
            return None
        if not self.vatable:
            return self.price_gross_eur
        rate = (self.vat_rate_pct or 0) / 100
        return round(self.price_gross_eur / (1 + rate), 2)

    @property
    def reclaimable_vat_eur(self):
        if self.price_gross_eur is None or not self.vatable:
            return None
        return round(self.price_gross_eur - self.price_net_eur, 2)
