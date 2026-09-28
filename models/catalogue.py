# -*- coding: utf-8 -*-
"""The car catalogue: brands and their models, one list for the whole company.

Every place that names a car points here — the car records, the supplier
adverts, the workbook's deposit / customs / price tables, the website cars and
what a lead asked for. Before this they were free text, and the same brand was
"Mercedes" in the workbook, "Mercedes-Benz" on a car and "مرسيدس" in a chat:
joins found nothing and nobody was told.

The website's own brand and model lists fill the catalogue (`website_id` keeps
the link, so a car can be sent there), but the catalogue is Genie's: a brand
the website does not carry is still a brand. Names are edited here; a website
sync links rows and adds missing ones, it never renames what the company named.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.fields import AttachmentForeignKeyField
from modules.base.models.base import BaseModel

ALIASES_HELP = _("Other spellings that mean this one, comma separated — e.g. Mercedes-Benz, مرسيدس بنز")


def _split(aliases):
    return [a.strip() for a in (aliases or '').split(',') if a.strip()]


class CarBrand(BaseModel):
    """A car make."""

    name = models.CharField(max_length=64, unique=True, verbose_name=_("Brand"))
    name_ar = models.CharField(max_length=64, blank=True, verbose_name=_("Name (Arabic)"))
    aliases = models.CharField(max_length=255, blank=True, verbose_name=_("Also matches"), help_text=ALIASES_HELP)
    website_id = models.PositiveIntegerField(
        null=True, blank=True, unique=True, verbose_name=_("Website id"),
        help_text=_("The brand's number on the company website. Empty when the website does not carry it"))
    logo = AttachmentForeignKeyField(related_name='+', upload_to='car_import/brands', allowed_types=['image'],
                                     verbose_name=_("Logo"))
    sequence = models.PositiveIntegerField(default=10, verbose_name=_("Order"))

    class Meta:
        verbose_name = _("Car brand")
        verbose_name_plural = _("Car brands")
        ordering = ['sequence', 'name']

    def __str__(self):
        return self.name

    def names(self):
        return [n for n in [self.name, self.name_ar] + _split(self.aliases) if n]

    def pre_save(self):
        super().pre_save()
        self.name = (self.name or '').strip()
        self.name_ar = (self.name_ar or '').strip()
        stored = type(self)._base_manager.filter(pk=self.pk).values_list('name', flat=True).first() if self.pk else None
        self._renamed = bool(self.pk) and stored != self.name

    def post_save(self):
        super().post_save()
        if getattr(self, '_renamed', False):
            from car_import.services import catalogue
            catalogue.refresh_names(brand=self)


class CarModel(BaseModel):
    """One model of a brand, e.g. Mercedes-Benz C200."""

    brand = models.ForeignKey(CarBrand, on_delete=models.PROTECT, related_name='car_models',
                              verbose_name=_("Brand"))
    name = models.CharField(max_length=128, verbose_name=_("Model"))
    name_ar = models.CharField(max_length=128, blank=True, verbose_name=_("Name (Arabic)"))
    aliases = models.CharField(max_length=255, blank=True, verbose_name=_("Also matches"), help_text=ALIASES_HELP)
    website_id = models.PositiveIntegerField(
        null=True, blank=True, unique=True, verbose_name=_("Website id"),
        help_text=_("The model's number on the company website. Empty when the website does not carry it"))
    #: "Mercedes-Benz C200" — what a picker shows where the brand is not beside it.
    display_name = models.CharField(max_length=200, blank=True, editable=False, db_index=True,
                                    verbose_name=_("Brand and model"))

    class Meta:
        verbose_name = _("Car model")
        verbose_name_plural = _("Car models")
        ordering = ['brand__sequence', 'brand__name', 'name']
        constraints = [models.UniqueConstraint(fields=['brand', 'name'], name='uniq_car_model_per_brand')]

    def __str__(self):
        return self.display_name or self.name

    def names(self):
        return [n for n in [self.name, self.name_ar] + _split(self.aliases) if n]

    def pre_save(self):
        super().pre_save()
        self.name = (self.name or '').strip()
        self.name_ar = (self.name_ar or '').strip()
        if not self.name:
            raise ValidationError({'name': _("A model needs a name.")})
        self.display_name = f'{self.brand.name} {self.name}'.strip() if self.brand_id else self.name
        stored = (type(self)._base_manager.filter(pk=self.pk).values_list('display_name', flat=True).first()
                  if self.pk else None)
        self._renamed = bool(self.pk) and stored != self.display_name

    def post_save(self):
        super().post_save()
        if getattr(self, '_renamed', False):
            from car_import.services import catalogue
            catalogue.refresh_names(car_model=self)
