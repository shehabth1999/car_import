# -*- coding: utf-8 -*-
"""Two marketplaces the company runs itself.

`ShowroomListing` is a car already in Egypt, sitting in the Berlin-or-Cairo
showroom with a price in pounds — a different animal from a `SupplierListing`,
which is a German advert the company might buy. One is stock, the other is
shopping.

`InitiativeListing` is a holder offering their deposit right for sale. The
initiative closed to new participants in 2024, so the only way in now is to buy
someone else's — which makes this a real market the company can broker, and the
thing agent A7 matches buyers into.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel


class ShowroomListing(BaseModel):
    """A car in Egypt, offered for sale."""

    STATE = [
        ('draft', _("Draft")),
        ('available', _("Available")),
        ('reserved', _("Reserved")),
        ('sold', _("Sold")),
        ('withdrawn', _("Withdrawn")),
    ]

    vehicle = models.ForeignKey('car_import.Vehicle', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='showroom_listings',
                                verbose_name=_("Car"))
    title = models.CharField(max_length=190, verbose_name=_("Title"))
    state = models.CharField(max_length=16, choices=STATE, default='draft', verbose_name=_("State"))

    price_egp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                    verbose_name=_("Price (EGP)"))
    negotiable = models.BooleanField(default=False, verbose_name=_("Negotiable"))

    licensed = models.BooleanField(default=False, verbose_name=_("Licensed"))
    protection_film = models.BooleanField(default=False, verbose_name=_("Protection film fitted"))
    mileage_km = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Odometer (km)"))
    location = models.CharField(max_length=128, blank=True, verbose_name=_("Where it is"))

    # The client's own site is the shop window; this flag is what the feed reads.
    published_to_website = models.BooleanField(default=False, verbose_name=_("On the website"))
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Published"))
    photos = models.JSONField(default=list, blank=True, verbose_name=_("Photos"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    reserved_for = models.ForeignKey('base.Partner', null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='car_import_reservations',
                                     verbose_name=_("Reserved for"))
    sold_deal = models.ForeignKey('car_import.CarDeal', null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name='showroom_sales',
                                  verbose_name=_("Sold on deal"))

    class Meta:
        verbose_name = _("Showroom car")
        verbose_name_plural = _("Showroom cars")
        ordering = ['-id']
        indexes = [models.Index(fields=['state', 'published_to_website'])]

    def __str__(self):
        return f'{self.title} — {self.price_egp or "?"} EGP'

    def pre_save(self):
        super().pre_save()
        from django.utils import timezone
        # Stamp the moment it went public, once. A listing that is unpublished
        # and republished keeps its first date, which is what "listed since"
        # means to a customer.
        if self.published_to_website and self.published_at is None:
            self.published_at = timezone.now()


class InitiativeListing(BaseModel):
    """A deposit right offered for sale by its holder."""

    STATE = [
        ('draft', _("Draft")),
        ('available', _("Available")),
        ('matched', _("Buyer found")),
        ('completed', _("Transferred")),
        ('withdrawn', _("Withdrawn")),
    ]

    initiative = models.ForeignKey('car_import.Initiative', on_delete=models.CASCADE,
                                   related_name='listings', verbose_name=_("Initiative"))
    state = models.CharField(max_length=16, choices=STATE, default='draft', verbose_name=_("State"))
    asking_price_egp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                           verbose_name=_("Asking price (EGP)"))
    # What the holder will accept: sell outright, or share the car's value.
    participation_terms = models.CharField(max_length=255, blank=True,
                                           verbose_name=_("Terms"))
    buyer = models.ForeignKey('base.Partner', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='car_import_initiative_purchases',
                              verbose_name=_("Buyer"))
    matched_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Matched"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Initiative for sale")
        verbose_name_plural = _("Initiatives for sale")
        ordering = ['-id']
        indexes = [models.Index(fields=['state'])]

    def __str__(self):
        holder = getattr(getattr(self.initiative, 'holder', None), 'name', '') or '—'
        return f'{holder} · {self.asking_price_egp or "?"} EGP'
