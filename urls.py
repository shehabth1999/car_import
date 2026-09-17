# -*- coding: utf-8 -*-
"""The extension's own routes. Not read by core: `patches.apply_url_patches`
inserts them into the root urlconf at startup, before the website catch-all."""
from django.urls import path

from . import pages

urlpatterns = [
    path('car-import/calculator/', pages.calculator_page, name='car_import_calculator'),
    path('car-import/calculator/compute/', pages.calculator_compute, name='car_import_calculator_compute'),
    path('car-import/calculator/save/', pages.calculator_save, name='car_import_calculator_save'),
]
