# -*- coding: utf-8 -*-
"""The extension's own routes. Not read by core: `patches.apply_url_patches`
inserts them into the root urlconf at startup, before the website catch-all."""
from django.urls import path

from . import pages, website_endpoints

urlpatterns = [
    path('car-import/calculator/', pages.calculator_page, name='car_import_calculator'),
    path('car-import/calculator/compute/', pages.calculator_compute, name='car_import_calculator_compute'),
    path('car-import/calculator/save/', pages.calculator_save, name='car_import_calculator_save'),
    # The company website's backend calls these (website_endpoints.py). Registered with AND
    # without the trailing slash: APPEND_SLASH turns a slash-less POST into a redirect that
    # drops the body.
    path('api/website/leads', website_endpoints.leads, name='car_import_website_leads'),
    path('api/website/leads/', website_endpoints.leads),
    path('api/website/tracking', website_endpoints.tracking, name='car_import_website_tracking'),
    path('api/website/tracking/', website_endpoints.tracking),
    path('api/website/ping', website_endpoints.ping, name='car_import_website_ping'),
    path('api/website/ping/', website_endpoints.ping),
]
