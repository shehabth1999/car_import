# -*- coding: utf-8 -*-
"""The lists the client kept under "Link Tracker" in Odoo.

In their Odoo the top menu called Link Tracker is not a link tracker: it is
where every pick-list an administrator maintains lives — the model years and
colours a lead can ask for, the ports and shippers a car travels through, who
is on hold, who is blacklisted. Sixteen entries; four of them already have a
table here (crm.UtmMedium, crm.UtmSource, CarBrand, CarModel) and the menu
points at those. These are the other twelve, field for field, so management
finds the lists they already keep.

Lists and nothing more, with two exceptions. No lead, deal or car points at
them yet — the colour, the year and the port on those records are what they
were before. The exceptions: `OnHoldSalesperson` — the lead assignment job
(services/lead_assignment.py) gives nobody on it a new lead — and
`EuMadeBrand` (2026-10-07), which the quoting tool reads for EUR 1.

No chatter on any of them, and class names that say whose they are: a model
named like another module's, both with chatter, once broke the system checks
here (see migration 0028).
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel


class PickList(BaseModel):
    """One list of names. `active` and `key` come with BaseModel."""

    name = models.CharField(max_length=128, verbose_name=_("Name"))

    class Meta:
        abstract = True
        ordering = ['name']

    def __str__(self):
        return self.name


# ── Cars ─────────────────────────────────────────────────────────────────────
class CarModelYear(PickList):
    """A model year the way sales writes it — text: "2026", "2025-2026", "Unspecified"."""

    class Meta(PickList.Meta):
        verbose_name = _("Car model year")
        verbose_name_plural = _("Car model years")


class CarColour(PickList):
    """A colour a customer can ask for."""

    class Meta(PickList.Meta):
        verbose_name = _("Car colour")
        verbose_name_plural = _("Car colours")


class CarTrimLevel(PickList):
    """A trim level, and what comes with it."""

    options_features = models.TextField(blank=True, verbose_name=_("Options/Features"))

    class Meta(PickList.Meta):
        verbose_name = _("Car trim level")
        verbose_name_plural = _("Car trim levels")


class CarBuyer(PickList):
    """Who a car is bought by: the owner (`name`), their company and its address."""

    company_name = models.CharField(max_length=255, blank=True, verbose_name=_("Company name"))
    address = models.CharField(max_length=255, blank=True, verbose_name=_("Address"))

    class Meta(PickList.Meta):
        verbose_name = _("Car buyer")
        verbose_name_plural = _("Car buyers")


class EuMadeBrand(BaseModel):
    """A brand whose cars are built inside the European Union.

    The client, 2026-10-07: «ندخل البراندات اللي بتتصنع داخل الاتحاد
    الأوروبي». It is what EUR 1 rests on — a car must be built in the EU for
    the certificate — so the quoting tool reads it: once this list has rows, a
    brand that is not on it is flagged to the assistant and to staff
    (`services/catalogue.made_in_eu`). An empty list flags nothing, so the
    tool says nothing until management has filled it in.
    """

    brand = models.OneToOneField('car_import.CarBrand', on_delete=models.CASCADE, related_name='eu_made',
                                 verbose_name=_("Brand"))
    note = models.CharField(max_length=190, blank=True, verbose_name=_("Note"),
                            help_text=_("Optional, e.g. which countries or which models"))

    class Meta:
        verbose_name = _("EU-made brand")
        verbose_name_plural = _("EU-made brands")
        ordering = ['brand__name']

    def __str__(self):
        return str(self.brand)


# ── Delivery ─────────────────────────────────────────────────────────────────
class ArrivalPort(PickList):
    """The port a car arrives at."""

    class Meta(PickList.Meta):
        verbose_name = _("Arrival port")
        verbose_name_plural = _("Arrival ports")


class ShippingDestination(PickList):
    """Where a shipment is bound for."""

    class Meta(PickList.Meta):
        verbose_name = _("Shipping destination")
        verbose_name_plural = _("Shipping destinations")


class InternationalShipper(PickList):
    """A company that ships the cars."""

    class Meta(PickList.Meta):
        verbose_name = _("International shipper")
        verbose_name_plural = _("International shippers")


class LoadingPort(PickList):
    """The port a car is loaded at. Odoo's menu calls this list "International Shipping"."""

    class Meta(PickList.Meta):
        verbose_name = _("Loading port")
        verbose_name_plural = _("Loading ports")


class CustomsClearancePerson(PickList):
    """Whoever clears a car through customs — a person or an employee, by name."""

    class Meta(PickList.Meta):
        verbose_name = _("Customs clearance person")
        verbose_name_plural = _("Customs clearance people")


# ── Opportunities ────────────────────────────────────────────────────────────
class OpportunityProductType(PickList):
    """What a lead is asking for: "Shipping", "Buy Car"."""

    class Meta(PickList.Meta):
        verbose_name = _("Product type")
        verbose_name_plural = _("Product types")


# ── Salespersons ─────────────────────────────────────────────────────────────
class OnHoldSalesperson(BaseModel):
    """A salesperson who gets no new leads for now. One row per person.

    Being on the list is the whole rule: `users_on_hold` in
    services/lead_assignment.py reads it on every run. `hidden` is carried over
    from Odoo and read by nothing — what it did there is not known.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+', verbose_name=_("Salesperson"),
        help_text=_("While a salesperson is on this list, the automatic lead assignment gives them no new leads. The leads they already have stay with them."))
    hidden = models.BooleanField(default=False, verbose_name=_("Hidden"),
                                 help_text=_("Kept as it was in Odoo. It has no effect here."))

    class Meta:
        verbose_name = _("On-hold salesperson")
        verbose_name_plural = _("On-hold salespeople")
        ordering = ['id']

    def __str__(self):
        return str(self.user)


# ── Blacklist ────────────────────────────────────────────────────────────────
class BlacklistedCustomer(PickList):
    """A customer on the blacklist, and the phone they are known by.

    A list only: nothing here refuses a lead or a chat because of it.
    """

    phone = models.CharField(max_length=32, blank=True, verbose_name=_("Phone"))

    class Meta(PickList.Meta):
        verbose_name = _("Blacklisted customer")
        verbose_name_plural = _("Blacklisted customers")
