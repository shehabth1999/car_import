# -*- coding: utf-8 -*-
"""The company's rules, as data instead of as code.

Every figure in here was a Python constant until now — the fee schedule and the
instalment terms lived in `tools/deal_tools.py`, which meant management could
not change a price without a developer, a review and a deploy, and nothing
recorded who changed what or when it started applying.

So each table carries `effective_from` / `effective_to`, and lookups ask for the
row in force on a date rather than "the row". A quote written in March stays
reproducible in June, which is the whole point: the client's own complaint about
their current process is that nobody can reconstruct how a price was reached.

Nothing here computes a price. These are the inputs; the pricing engine that
consumes them comes next, and it cannot ship until the client answers the
open questions (the down-payment formula, and whether the customs figure is the
amount payable or the value the rate applies to).
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel


class EffectiveMixin(models.Model):
    """Dated rows: what was true then, not only what is true now."""

    effective_from = models.DateField(null=True, blank=True, verbose_name=_("In force from"))
    effective_to = models.DateField(null=True, blank=True, verbose_name=_("In force until"))
    source_note = models.CharField(max_length=190, blank=True, verbose_name=_("Where this came from"),
                                   help_text=_("e.g. owner's answers 2026-09-14, the values workbook"))

    class Meta:
        abstract = True

    @classmethod
    def in_force(cls, on=None, **filters):
        """Rows valid on a date — today when none is given."""
        from django.utils import timezone
        when = on or timezone.localdate()
        return (cls.objects.filter(**filters)
                .filter(models.Q(effective_from__isnull=True) | models.Q(effective_from__lte=when))
                .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=when)))


# ═══════════════════════════════════════════════════════════════════════════
# 1. the routes a car can travel
# ═══════════════════════════════════════════════════════════════════════════
class ImportProgram(BaseModel, EffectiveMixin):
    """One of the ways a car may legally be imported."""

    code = models.CharField(max_length=32, unique=True, verbose_name=_("Code"))
    name = models.CharField(max_length=128, verbose_name=_("Name"))
    name_en = models.CharField(max_length=128, blank=True, verbose_name=_("Name (English)"))
    sequence = models.PositiveIntegerField(default=10, verbose_name=_("Sequence"))

    # The disability route is suspended by law, not by us — it must refuse
    # loudly rather than quietly produce a price nobody can honour.
    is_blocked = models.BooleanField(default=False, verbose_name=_("Suspended"))
    blocked_reason = models.CharField(max_length=255, blank=True, verbose_name=_("Why suspended"))
    requires_management_approval = models.BooleanField(
        default=False, verbose_name=_("Needs management approval"))

    requires_zero_km = models.BooleanField(default=False, verbose_name=_("Must be a brand-new car"))
    requires_current_model_year = models.BooleanField(
        default=False, verbose_name=_("Must be this year's model"))
    min_model_year = models.PositiveIntegerField(null=True, blank=True,
                                                 verbose_name=_("Oldest model year allowed"))
    max_cc = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Engine limit (cc)"))
    instalments_allowed = models.BooleanField(default=True, verbose_name=_("Instalments possible"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Import programme")
        verbose_name_plural = _("Import programmes")
        ordering = ['sequence', 'code']

    def __str__(self):
        return self.name or self.code


class TaxRule(BaseModel, EffectiveMixin):
    """(programme, engine size, EUR 1) → the rate that applies."""

    program = models.ForeignKey(ImportProgram, on_delete=models.CASCADE, related_name='tax_rules',
                                verbose_name=_("Programme"))
    cc_min = models.PositiveIntegerField(default=0, verbose_name=_("From (cc)"))
    cc_max = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("To (cc)"))
    with_eur1 = models.BooleanField(default=False, verbose_name=_("With EUR 1 certificate"))
    rate_pct = models.DecimalField(max_digits=6, decimal_places=2, verbose_name=_("Rate %"))

    class Meta:
        verbose_name = _("Tax rule")
        verbose_name_plural = _("Tax rules")
        ordering = ['program', 'cc_min', '-with_eur1']

    def __str__(self):
        ceiling = self.cc_max or '∞'
        return f'{self.program} {self.cc_min}–{ceiling}cc {"EUR1" if self.with_eur1 else "no EUR1"}: {self.rate_pct}%'


class Eur1Rule(BaseModel, EffectiveMixin):
    """The three conditions for the certificate, and who may use it."""

    name = models.CharField(max_length=128, default='EUR 1', verbose_name=_("Name"))
    built_in_eu_required = models.BooleanField(default=True, verbose_name=_("Built in the EU"))
    built_for_eu_required = models.BooleanField(default=True, verbose_name=_("Built for the EU market"))
    exported_from_eu_port_required = models.BooleanField(
        default=True, verbose_name=_("Exported from an EU port"))
    eligible_residencies = models.JSONField(default=list, blank=True,
                                            verbose_name=_("Residencies that qualify"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("EUR 1 rule")
        verbose_name_plural = _("EUR 1 rules")

    def __str__(self):
        return self.name


# ═══════════════════════════════════════════════════════════════════════════
# 2. the numbers, from the client's own workbook
# ═══════════════════════════════════════════════════════════════════════════
class DepositTier(BaseModel, EffectiveMixin):
    """The initiative deposit for a model, year, tier and region."""

    TIER = [('medium', _("Medium")), ('full', _("Full"))]
    REGION = [('europe', _("Inside Europe")), ('outside', _("Outside Europe"))]

    make = models.CharField(max_length=64, verbose_name=_("Make"))
    model = models.CharField(max_length=128, verbose_name=_("Model"))
    model_year = models.PositiveIntegerField(verbose_name=_("Model year"))
    tier = models.CharField(max_length=16, choices=TIER, verbose_name=_("Tier"))
    region = models.CharField(max_length=16, choices=REGION, verbose_name=_("Region"))
    deposit_usd = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Deposit (USD)"))

    class Meta:
        verbose_name = _("Deposit value")
        verbose_name_plural = _("Deposit values")
        ordering = ['make', 'model', 'model_year', 'tier', 'region']
        constraints = [
            models.UniqueConstraint(fields=['make', 'model', 'model_year', 'tier', 'region'],
                                    name='uniq_deposit_tier'),
        ]

    def __str__(self):
        return f'{self.make} {self.model} {self.model_year} {self.get_tier_display()} {self.get_region_display()}: ${self.deposit_usd}'


class CustomsValuation(BaseModel, EffectiveMixin):
    """The official customs figure per model and year.

    Question V1 is answered (client, 2026-09-16): this number is **the amount
    actually paid**, not a value a rate is applied to. So 15,800 € against a
    C200 is 15,800 € of customs, full stop — and the engine may use it
    directly instead of refusing.

    The same answer carried a warning worth keeping in the model rather than
    in somebody's memory: *"القيم متغيرة على حسب تحديثات الحكومة"*. The figure
    moves when the government moves it, which is exactly why these rows are
    dated. A new government table closes the old rows and opens new ones; it
    never overwrites them, so a deal quoted under last quarter's table can
    still be explained under this quarter's.
    """

    BASIS = [
        ('payable', _("The amount payable")),
        ('valuation', _("The value the rate applies to")),
        ('unknown', _("Not yet confirmed")),
    ]

    make = models.CharField(max_length=64, verbose_name=_("Make"))
    model = models.CharField(max_length=128, verbose_name=_("Model"))
    model_year = models.PositiveIntegerField(verbose_name=_("Model year"))
    value_eur = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Value (EUR)"))
    basis = models.CharField(max_length=16, choices=BASIS, default='payable',
                             verbose_name=_("This number is"),
                             help_text=_("Confirmed by the client on 16 September 2026: the "
                                         "figures in the initiative workbook are the amount "
                                         "actually paid"))

    class Meta:
        verbose_name = _("Customs value")
        verbose_name_plural = _("Customs values")
        ordering = ['make', 'model', 'model_year']
        constraints = [
            models.UniqueConstraint(fields=['make', 'model', 'model_year'], name='uniq_customs_value'),
        ]

    def __str__(self):
        return f'{self.make} {self.model} {self.model_year}: {self.value_eur} €'


class ModelPriceRange(BaseModel, EffectiveMixin):
    """Typical market range per model and year — for "from about …" answers."""

    make = models.CharField(max_length=64, verbose_name=_("Make"))
    model = models.CharField(max_length=128, verbose_name=_("Model"))
    model_year = models.PositiveIntegerField(verbose_name=_("Model year"))
    price_from_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                         verbose_name=_("From (EUR)"))
    price_to_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                       verbose_name=_("To (EUR)"))
    egypt_price_egp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                          verbose_name=_("Egypt price (EGP)"))
    hp = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Power (hp)"))
    cc_rounded = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Engine (cc, rounded)"),
                                             help_text=_("The workbook rounds to 1500/2000/3000 — the "
                                                         "exact displacement comes from the car's papers"))
    fuel = models.CharField(max_length=32, blank=True, verbose_name=_("Fuel"))

    class Meta:
        verbose_name = _("Model price range")
        verbose_name_plural = _("Model price ranges")
        ordering = ['make', 'model', 'model_year']
        constraints = [
            models.UniqueConstraint(fields=['make', 'model', 'model_year'], name='uniq_model_price_range'),
        ]

    def __str__(self):
        return f'{self.make} {self.model} {self.model_year}'


# ═══════════════════════════════════════════════════════════════════════════
# 3. what the company charges, and how it may be paid
# ═══════════════════════════════════════════════════════════════════════════
class FeeSchedule(BaseModel, EffectiveMixin):
    """One chargeable line, dated. Replaces the FEES constant in the tools."""

    APPLIES_TO = [
        ('always', _("Every deal")),
        ('with_eur1', _("Only with EUR 1")),
        ('optional', _("Optional extra")),
        ('on_request', _("Only when asked for")),
    ]

    code = models.CharField(max_length=64, unique=True, verbose_name=_("Code"))
    name = models.CharField(max_length=190, verbose_name=_("Name"))
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                 verbose_name=_("Amount"))
    amount_to = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                    verbose_name=_("Up to"), help_text=_("For a range, e.g. protection film"))
    currency = models.ForeignKey('base.Currency', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='+', verbose_name=_("Currency"))
    applies_to = models.CharField(max_length=16, choices=APPLIES_TO, default='always',
                                  verbose_name=_("Applies"))
    # Some figures exist but may never be said to a customer — the licence cost
    # itself is the client's own rule, not ours.
    quotable_to_customer = models.BooleanField(default=True, verbose_name=_("May be quoted"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Fee")
        verbose_name_plural = _("Fee schedule")
        ordering = ['code']

    def __str__(self):
        return f'{self.name}: {self.amount} {getattr(self.currency, "code", "")}'


class FinancingPlan(BaseModel, EffectiveMixin):
    """A plan the assistant may describe. Replaces the INSTALMENTS constant."""

    code = models.CharField(max_length=32, unique=True, verbose_name=_("Code"))
    name = models.CharField(max_length=190, verbose_name=_("Name"))
    available = models.BooleanField(default=True, verbose_name=_("On offer"))
    down_payment_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                           verbose_name=_("Down payment %"))
    term_months = models.JSONField(default=list, blank=True, verbose_name=_("Terms (months)"))
    rate_pct_flat = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                        verbose_name=_("Flat rate % per year"))
    cheques_required = models.BooleanField(default=False, verbose_name=_("Cheques required"))
    first_instalment_note = models.CharField(max_length=190, blank=True,
                                             verbose_name=_("First instalment"))
    covers = models.CharField(max_length=255, blank=True, verbose_name=_("What it covers"))
    not_available_when = models.CharField(max_length=255, blank=True,
                                          verbose_name=_("Not available when"))
    # The calculation method stays empty until the client answers F1–F3; the
    # assistant states terms and never computes an amount.
    amount_policy = models.CharField(
        max_length=255, blank=True, verbose_name=_("Who computes the instalment"),
        default="A colleague gives the exact amount — never the assistant.")
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Financing plan")
        verbose_name_plural = _("Financing plans")
        ordering = ['code']

    def __str__(self):
        return self.name


class FirstOwnerDiscount(BaseModel, EffectiveMixin):
    """5 % per year of ownership, between five and nine years."""

    years_owned = models.PositiveIntegerField(verbose_name=_("Years owned"))
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_("Discount %"))

    class Meta:
        verbose_name = _("First-owner discount")
        verbose_name_plural = _("First-owner discounts")
        ordering = ['years_owned']
        constraints = [
            models.UniqueConstraint(fields=['years_owned'], name='uniq_first_owner_years'),
        ]

    def __str__(self):
        return f'{self.years_owned} years: {self.discount_pct}%'


class FxReference(BaseModel, EffectiveMixin):
    """The manager's rate of the day. A quoting reference, never a ledger.

    Every EGP figure the company gives is indicative at today's rate and carries
    a conversion commission; both travel with the rate so a quote can say so.
    """

    currency_from = models.ForeignKey('base.Currency', null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name='+', verbose_name=_("From"))
    currency_to = models.ForeignKey('base.Currency', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+', verbose_name=_("To"))
    rate = models.DecimalField(max_digits=14, decimal_places=6, verbose_name=_("Rate"))
    commission_pct_min = models.DecimalField(max_digits=5, decimal_places=2, default=1.5,
                                             verbose_name=_("Commission % from"))
    commission_pct_max = models.DecimalField(max_digits=5, decimal_places=2, default=2,
                                             verbose_name=_("Commission % to"))
    set_by = models.ForeignKey('base.User', null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='car_import_fx_rates', verbose_name=_("Set by"))
    note = models.CharField(max_length=190, blank=True, verbose_name=_("Note"))

    class Meta:
        verbose_name = _("Exchange rate")
        verbose_name_plural = _("Exchange rates")
        ordering = ['-effective_from', '-id']

    def __str__(self):
        return f'{getattr(self.currency_from, "code", "?")}/{getattr(self.currency_to, "code", "?")} {self.rate}'

    def pre_save(self):
        """Publishing a rate is the company manager's decision, not an agent's.

        The client's matrix: *"Transfer / تدبير rate and its 1.5–2 % commission —
        Company manager."* Asked once, on creation: a rate that is on the table
        is a rate somebody will quote within the hour.
        """
        super().pre_save()
        from car_import.services import currencies
        if self.currency_from_id is None:
            self.currency_from = currencies.eur()
        if self.currency_to_id is None:
            self.currency_to = currencies.egp()
        if self.pk:
            return
        from .approval import require
        require('fx_rate', None, field='rate',
                reason=_("Publish %(pair)s at %(rate)s") % {
                    'pair': f'{getattr(self.currency_from, "code", "?")}/{getattr(self.currency_to, "code", "?")}',
                    'rate': self.rate},
                user=getattr(getattr(self, 'env', None), 'user', None))
