# -*- coding: utf-8 -*-
"""The company website (khaledautomobilegmbh.de) as Genie sees it.

Two directions, one connection record:

* **Genie → website.** The website's own API (Laravel + Sanctum, documented in
  the developer's "Khaled Automobile GmbH API" collection) publishes cars.
  Genie replaces the Odoo link that used to feed it: `WebsiteCar` mirrors a
  website vehicle field for field, is the master copy, and is pushed back on
  save (`services/website_api.py`). `WebsiteLookup` holds the website's own
  id/name lists (brands, models, fuels…), because every id the website accepts
  is one of ITS database ids.
* **Website → Genie.** Two endpoints Genie serves to the website's backend:
  the lead webhook (every form a visitor submits becomes a CRM lead) and the
  tracking API (the "track your car" page). Both are authenticated with the
  single `inbound_api_key` on the connection record.

Nothing here talks HTTP; the models only hold state and expose buttons.
"""
import secrets

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.base.decorators import action, onchange
from modules.base.fields import AttachmentForeignKeyField, AttachmentManyToManyField
from modules.base.models.base import BaseModel


def new_inbound_key():
    return 'gka_' + secrets.token_urlsafe(32)


def _message(text, ok=True):
    return {'status': ok, 'open_mode': 'message', 'message': str(text), 'data': {},
            'on_success': {'type': 'refresh'}}


class WebsiteConnection(BaseModel):
    """The one connection to the company website. There is exactly one row."""

    name = models.CharField(max_length=128, default='khaledautomobilegmbh.de', verbose_name=_("Name"))
    base_url = models.URLField(
        max_length=255, default='https://khaledautomobilegmbh.de/api', verbose_name=_("Website API URL"),
        help_text=_("The website API root, ending in /api — no trailing slash"))
    api_email = models.CharField(max_length=190, blank=True, verbose_name=_("Website API login (email)"))
    api_password = models.CharField(
        max_length=255, blank=True, verbose_name=_("Website API password"),
        help_text=_("The website account Genie logs in with. Kept on this screen only — never in code"))
    push_enabled = models.BooleanField(
        default=False, verbose_name=_("Send changes to the website"),
        help_text=_("Off: Genie only READS from the website. On: saving a website car in Genie updates "
                    "the live website. Switch on only after the website developer confirms the account "
                    "may add and edit vehicles"))
    import_new_cars_nightly = models.BooleanField(
        default=True, verbose_name=_("Bring in cars added on the website"),
        help_text=_("Every night, cars created directly in the website dashboard are added to Genie. "
                    "Existing cars are never overwritten by this"))

    # ── the other direction ─────────────────────────────────────────────────
    inbound_api_key = models.CharField(
        max_length=96, blank=True, verbose_name=_("Key the website sends to Genie"),
        help_text=_("Give this to the website developer privately. The website sends it with every lead "
                    "and every tracking request. Regenerating it stops the old key at once"))
    leads_enabled = models.BooleanField(default=True, verbose_name=_("Accept leads from the website"))
    tracking_enabled = models.BooleanField(default=True, verbose_name=_("Answer tracking requests"))

    # ── bookkeeping, never typed ────────────────────────────────────────────
    token = models.TextField(blank=True, editable=False, verbose_name=_("Current token"))
    token_obtained_at = models.DateTimeField(null=True, blank=True, editable=False,
                                             verbose_name=_("Logged in at"))
    last_ok_at = models.DateTimeField(null=True, blank=True, editable=False,
                                      verbose_name=_("Last successful call"))
    last_error = models.TextField(blank=True, editable=False, verbose_name=_("Last error"))
    lookups_synced_at = models.DateTimeField(null=True, blank=True, editable=False,
                                             verbose_name=_("Lists synced at"))
    cars_imported_at = models.DateTimeField(null=True, blank=True, editable=False,
                                            verbose_name=_("Cars imported at"))

    class Meta:
        verbose_name = _("Website connection")
        verbose_name_plural = _("Website connection")

    def __str__(self):
        return self.name or 'website'

    @classmethod
    def get(cls):
        row = cls.objects.order_by('id').first()
        if row is None:
            row = cls(inbound_api_key=new_inbound_key())
            row.save()
        return row

    def pre_save(self):
        super().pre_save()
        if self.base_url:
            self.base_url = self.base_url.strip().rstrip('/')
            if not self.base_url.startswith('https://'):
                raise ValidationError({'base_url': _("The website API address must start with https://")})
        if not self.inbound_api_key:
            self.inbound_api_key = new_inbound_key()
        if self.pk:
            stored = type(self)._base_manager.filter(pk=self.pk).values(
                'base_url', 'api_email', 'api_password').first() or {}
            if any(stored.get(f) != getattr(self, f) for f in ('base_url', 'api_email', 'api_password')):
                self.token = ''            # new credentials → log in again
                self.token_obtained_at = None

    # ── buttons ─────────────────────────────────────────────────────────────
    @action
    def action_test_connection(queryset):
        """Log in to the website and read the account."""
        from car_import.services import website_api
        try:
            user = website_api.WebsiteClient().current_user()
        except website_api.WebsiteApiError as exc:
            return _message(_("The website refused: %(error)s") % {'error': exc}, ok=False)
        return _message(_("Connected to the website as %(name)s (%(email)s).")
                        % {'name': user.get('name', ''), 'email': user.get('email', '')})

    @action
    def action_sync_lookups(queryset):
        """Read the website's lists: brands, models, fuels, gearboxes…"""
        from car_import.services import website_api
        try:
            counts = website_api.sync_lookups()
        except website_api.WebsiteApiError as exc:
            return _message(_("The lists could not be read: %(error)s") % {'error': exc}, ok=False)
        return _message(_("Website lists updated: %(counts)s")
                        % {'counts': ', '.join(f'{k} {v}' for k, v in counts.items())})

    @action
    def action_import_cars(queryset):
        """Bring every website car into Genie. Genie's copies are overwritten with the website's."""
        from car_import.services import website_api
        try:
            result = website_api.import_cars(mode='all')
        except website_api.WebsiteApiError as exc:
            return _message(_("The cars could not be read: %(error)s") % {'error': exc}, ok=False)
        return _message(_("Website cars: %(created)d added, %(updated)d updated, %(review)d need review.")
                        % result)

    @action
    def action_regenerate_inbound_key(queryset):
        """Issue a new key for the website. The old one stops working at once."""
        for row in queryset:
            row.inbound_api_key = new_inbound_key()
            row.save()
        return _message(_("A new key was issued. Give it to the website developer; the old key no longer works."))

    @action
    def action_push_pending(queryset):
        """Send every website car that has unsent changes."""
        from car_import.tasks import push_website_car
        pending = list(WebsiteCar.objects.filter(sync_state__in=['pending', 'error']).values_list('id', flat=True))
        for pk in pending:
            push_website_car.delay(pk)
        return _message(_("%(count)d car(s) queued for the website.") % {'count': len(pending)})


class WebsiteLookup(BaseModel):
    """One entry of a website list, with the website's own id."""

    #: Brands and models are not here: they live in the car catalogue
    #: (CarBrand / CarModel), which the website's brand and model lists fill.
    KIND = [
        ('category', _("Category")),
        ('origin', _("Origin")),
        ('country', _("Car location")),
        ('fuel', _("Fuel")),
        ('bodytype', _("Body type")),
        ('gearbox', _("Gearbox")),
        ('engine', _("Engine")),
        ('extra_option', _("Extra option")),
        ('vehicle_option', _("Vehicle option")),
    ]
    #: kind → the website's input-list path
    ENDPOINTS = {
        'category': 'categories', 'origin': 'origins',
        'country': 'countries', 'fuel': 'fuels', 'bodytype': 'body-types', 'gearbox': 'gearboxes',
        'engine': 'engines', 'extra_option': 'car-extra-options', 'vehicle_option': 'vehicle-options',
    }

    kind = models.CharField(max_length=16, choices=KIND, db_index=True, verbose_name=_("List"))
    website_id = models.PositiveIntegerField(verbose_name=_("Website id"))
    name_en = models.CharField(max_length=190, blank=True, verbose_name=_("Name (English)"))
    name_ar = models.CharField(max_length=190, blank=True, verbose_name=_("Name (Arabic)"))
    aliases = models.CharField(
        max_length=255, blank=True, verbose_name=_("Also matches"),
        help_text=_("Other spellings Genie should match to this entry, comma separated — "
                    "e.g. Mercedes-Benz, Mercedes Benz"))
    is_active = models.BooleanField(default=True, verbose_name=_("Still on the website"))
    synced_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name=_("Synced at"))

    class Meta:
        verbose_name = _("Website list entry")
        verbose_name_plural = _("Website lists")
        ordering = ['kind', 'name_en', 'website_id']
        constraints = [models.UniqueConstraint(fields=['kind', 'website_id'], name='uniq_website_lookup')]

    def __str__(self):
        return self.name_en or self.name_ar or f'#{self.website_id}'

    def names(self):
        out = [self.name_en, self.name_ar] + [a.strip() for a in (self.aliases or '').split(',')]
        return [n for n in out if n]


class WebsiteCar(BaseModel):
    """One vehicle on the website — Genie's master copy of it."""

    WEBSITE_STATUS = [
        ('avalible', _("Available")),          # the website's own spelling, kept verbatim
        ('Available for import', _("Available for import")),
        ('Available for immediate delivery', _("Available for immediate delivery")),
        ('booked', _("Booked")),
        ('sold', _("Sold")),
    ]
    SEAT = [(s, s) for s in ('2-seater', '4-seater', '5-seater', '7-seater', '8-seater', '9-seater')]
    SYNC = [
        ('draft', _("Not on the website yet")),
        ('pending', _("Waiting to be sent")),
        ('synced', _("Up to date")),
        ('error', _("Sending failed")),
    ]

    website_id = models.PositiveIntegerField(null=True, blank=True, unique=True, editable=False,
                                             verbose_name=_("Website id"))
    vehicle = models.ForeignKey('car_import.Vehicle', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='website_cars', verbose_name=_("Car in Genie"))

    title_ar = models.CharField(max_length=255, blank=True, verbose_name=_("Title (Arabic)"))
    title_en = models.CharField(max_length=255, blank=True, verbose_name=_("Title (English)"))
    description_ar = models.TextField(blank=True, verbose_name=_("Description (Arabic)"))
    description_en = models.TextField(blank=True, verbose_name=_("Description (English)"))

    serial = models.CharField(max_length=255, blank=True, db_index=True, verbose_name=_("Chassis number"),
                              help_text=_("The website refuses a chassis number another car already used — "
                                          "even a deleted one"))
    year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Model year"))
    price = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                verbose_name=_("Price"))
    currency = models.ForeignKey('base.Currency', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='+', verbose_name=_("Currency"), editable=False,
                                 help_text=_("Set by the location: Egypt is Egyptian pounds, anywhere else euros"))

    location = models.ForeignKey(WebsiteLookup, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='+', verbose_name=_("Car location"))
    category = models.ForeignKey(WebsiteLookup, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='+', verbose_name=_("Category"))
    brand = models.ForeignKey('car_import.CarBrand', null=True, blank=True, on_delete=models.PROTECT,
                              related_name='website_cars', verbose_name=_("Brand"))
    car_model = models.ForeignKey('car_import.CarModel', null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='website_cars', verbose_name=_("Model"))
    origin = models.ForeignKey(WebsiteLookup, null=True, blank=True, on_delete=models.PROTECT,
                               related_name='+', verbose_name=_("Origin"))
    gearbox = models.ForeignKey(WebsiteLookup, null=True, blank=True, on_delete=models.PROTECT,
                                related_name='+', verbose_name=_("Gearbox"))
    bodytype = models.ForeignKey(WebsiteLookup, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='+', verbose_name=_("Body type"))
    engine = models.ForeignKey(WebsiteLookup, null=True, blank=True, on_delete=models.PROTECT,
                               related_name='+', verbose_name=_("Engine"))
    fuel = models.ForeignKey(WebsiteLookup, null=True, blank=True, on_delete=models.PROTECT,
                             related_name='+', verbose_name=_("Fuel"))
    extra_options = models.ManyToManyField(WebsiteLookup, blank=True, related_name='+',
                                           verbose_name=_("Extra options"))

    seat = models.CharField(max_length=16, choices=SEAT, blank=True, verbose_name=_("Seats"))
    distance = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Mileage (km)"))
    video_link = models.URLField(max_length=255, blank=True, verbose_name=_("Video link"))
    visible = models.BooleanField(default=False, verbose_name=_("Shown on the website"),
                                  help_text=_("Off hides the car from visitors. Genie never deletes a website "
                                              "car: a deleted car's chassis number can never be used again"))
    website_status = models.CharField(max_length=40, choices=WEBSITE_STATUS, default='avalible',
                                      editable=False, verbose_name=_("Status on the website"))
    odoo_id = models.PositiveIntegerField(null=True, blank=True, editable=False,
                                          verbose_name=_("Old Odoo id"))

    # ── pictures ────────────────────────────────────────────────────────────
    main_image = AttachmentForeignKeyField(
        related_name='+', upload_to='car_import/website/main', allowed_types=['image'],
        verbose_name=_("New main photo"),
        help_text=_("Replaces the website's main photo on the next send"))
    gallery = AttachmentManyToManyField(
        related_name='+', upload_to='car_import/website/gallery', allowed_types=['image'], blank=True,
        verbose_name=_("New gallery photos"),
        help_text=_("Added to the website gallery on the next send. The website cannot remove "
                    "gallery photos through its API"))
    site_image_url = models.URLField(max_length=500, blank=True, editable=False,
                                     verbose_name=_("Main photo on the website"))
    site_gallery_urls = models.JSONField(default=list, blank=True, editable=False,
                                         verbose_name=_("Gallery on the website"))
    sent_main_image_id = models.PositiveIntegerField(null=True, blank=True, editable=False)
    sent_gallery_ids = models.JSONField(default=list, blank=True, editable=False)

    # ── sync state ──────────────────────────────────────────────────────────
    sync_state = models.CharField(max_length=16, choices=SYNC, default='draft', editable=False,
                                  verbose_name=_("Website sync"))
    last_error = models.TextField(blank=True, editable=False, verbose_name=_("Last sending error"))
    last_synced_at = models.DateTimeField(null=True, blank=True, editable=False,
                                          verbose_name=_("Last synced"))
    needs_review = models.BooleanField(default=False, verbose_name=_("Needs review"))
    review_reason = models.CharField(max_length=255, blank=True, verbose_name=_("Why"))

    class Meta:
        verbose_name = _("Website car")
        verbose_name_plural = _("Website cars")
        ordering = ['-website_id', '-id']
        indexes = [models.Index(fields=['sync_state']), models.Index(fields=['visible', 'website_status'])]

    def __str__(self):
        return self.title_en or self.title_ar or self.serial or f'#{self.pk}'

    #: Set by the import so a save that COPIES the website does not send it back.
    _from_site = False
    #: Fields whose change means "send this to the website".
    PUSHED_FIELDS = ('title_ar', 'title_en', 'description_ar', 'description_en', 'serial', 'year', 'price',
                     'location_id', 'category_id', 'brand_id', 'car_model_id', 'origin_id', 'gearbox_id',
                     'bodytype_id', 'engine_id', 'fuel_id', 'seat', 'distance', 'video_link', 'visible',
                     'main_image_id')

    @property
    def is_egypt(self):
        return bool(self.location_id and self.location.website_id == 1)

    @onchange('brand')
    def _onchange_brand(self):
        if self.car_model_id and self.brand_id and self.car_model.brand_id != self.brand_id:
            return {'value': {'car_model': None}}
        return None

    @onchange('car_model')
    def _onchange_car_model(self):
        if self.car_model_id and self.car_model.brand_id != self.brand_id:
            return {'value': {'brand': self.car_model.brand}}
        return None

    def pre_save(self):
        super().pre_save()
        if self.serial:
            self.serial = self.serial.strip().upper().replace(' ', '')
        if self.price is not None and self.price < 0:
            raise ValidationError({'price': _("A price cannot be negative.")})
        if self.car_model_id and not self.brand_id:
            self.brand_id = self.car_model.brand_id
        if not self._from_site and self.car_model_id and self.car_model.brand_id != self.brand_id:
            raise ValidationError({'car_model': _("This model belongs to another brand.")})
        from car_import.services import currencies
        if self.location_id:
            self.currency = currencies.egp() if self.is_egypt else currencies.eur()
        self._pushed_fields_changed = self._changed_pushed_fields()
        if not self._from_site and self._pushed_fields_changed and self.sync_state != 'draft':
            self.sync_state = 'pending'

    def _changed_pushed_fields(self):
        if not self.pk:
            return list(self.PUSHED_FIELDS)
        stored = type(self)._base_manager.filter(pk=self.pk).values(*self.PUSHED_FIELDS).first() or {}
        return [f for f in self.PUSHED_FIELDS if stored.get(f) != getattr(self, f)]

    def post_save(self):
        super().post_save()
        if self._from_site or not getattr(self, '_pushed_fields_changed', None):
            return
        if self.sync_state not in ('pending',):
            return
        from car_import.services import website_api
        website_api.schedule_push(self.pk)

    # ── buttons ─────────────────────────────────────────────────────────────
    @action
    def action_send_to_website(queryset):
        """Send this car to the website now (creates it there if it is new)."""
        from car_import.services import website_api
        done, failed = 0, []
        for car in queryset:
            outcome = website_api.push_car(car)
            if outcome.get('ok'):
                done += 1
            else:
                failed.append(f'{car}: {outcome.get("error")}')
        message = _("Sent %(count)d car(s) to the website.") % {'count': done}
        if failed:
            message += '\n' + '\n'.join(failed)
        return _message(message, ok=bool(done))

    @action
    def action_hide(queryset):
        """Hide from website visitors (the car is kept; nothing is deleted)."""
        for car in queryset:
            car.visible = False
            car.sync_state = 'pending' if car.website_id else car.sync_state
            car.save()
        return _message(_("Hidden. The website updates on the next send."))

    @action
    def action_show(queryset):
        """Show to website visitors."""
        for car in queryset:
            car.visible = True
            car.sync_state = 'pending' if car.website_id else car.sync_state
            car.save()
        return _message(_("Shown. The website updates on the next send."))

    @action
    def action_mark_sold(queryset):
        """Mark as sold on the website. The website cannot undo this."""
        from car_import.services import website_api
        done, failed = 0, []
        for car in queryset:
            outcome = website_api.mark_sold(car)
            if outcome.get('ok'):
                done += 1
            else:
                failed.append(f'{car}: {outcome.get("error")}')
        message = _("Marked %(count)d car(s) sold on the website.") % {'count': done}
        if failed:
            message += '\n' + '\n'.join(failed)
        return _message(message, ok=bool(done))

    @action
    def action_link_vehicle(queryset):
        """Create (or find) the Genie car record for this website car."""
        from car_import.services import website_api
        linked = sum(1 for car in queryset if website_api.ensure_vehicle(car) is not None)
        return _message(_("Linked %(count)d car(s).") % {'count': linked})


class WebsiteSubmission(BaseModel):
    """One form a website visitor sent, as it arrived — the lead it became is linked."""

    FORM = [
        ('vehicle_request', _("Vehicle request")),
        ('car_inquiry', _("Question about a car")),
        ('contact', _("Contact form")),
        ('other', _("Other")),
    ]

    form = models.CharField(max_length=24, choices=FORM, default='vehicle_request', verbose_name=_("Form"))
    submission_id = models.CharField(max_length=100, null=True, blank=True, unique=True,
                                     verbose_name=_("Website reference"))
    name = models.CharField(max_length=190, blank=True, verbose_name=_("Name"))
    phone = models.CharField(max_length=40, blank=True, verbose_name=_("Phone"))
    email = models.CharField(max_length=190, blank=True, verbose_name=_("Email"))
    car_wanted = models.CharField(max_length=255, blank=True, verbose_name=_("Car asked about"))
    message = models.TextField(blank=True, verbose_name=_("Message"))
    website_car = models.ForeignKey(WebsiteCar, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='submissions', verbose_name=_("Website car"))
    partner = models.ForeignKey('base.Partner', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='+', verbose_name=_("Customer"))
    lead = models.ForeignKey('crm.Lead', null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='+', verbose_name=_("Lead"))
    is_duplicate = models.BooleanField(default=False, verbose_name=_("Repeat of an earlier request"))
    payload = models.JSONField(default=dict, blank=True, editable=False, verbose_name=_("What the website sent"))
    remote_ip = models.CharField(max_length=64, blank=True, editable=False, verbose_name=_("Sent from"))

    class Meta:
        verbose_name = _("Website request")
        verbose_name_plural = _("Website requests")
        ordering = ['-id']
        indexes = [models.Index(fields=['phone', 'created_at'])]

    def __str__(self):
        return f'{self.get_form_display()} — {self.name or self.phone}'


class WebsiteApiLog(BaseModel):
    """Every call between Genie and the website, both ways. Kept 90 days."""

    DIRECTION = [('out', _("Genie → website")), ('in', _("Website → Genie"))]

    direction = models.CharField(max_length=4, choices=DIRECTION, verbose_name=_("Direction"))
    method = models.CharField(max_length=8, verbose_name=_("Method"))
    path = models.CharField(max_length=255, verbose_name=_("Path"))
    status_code = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("HTTP status"))
    ok = models.BooleanField(default=False, verbose_name=_("Succeeded"))
    duration_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Took (ms)"))
    request_body = models.JSONField(null=True, blank=True, verbose_name=_("Request"))
    response_body = models.JSONField(null=True, blank=True, verbose_name=_("Response"))
    error = models.TextField(blank=True, verbose_name=_("Error"))
    object_ref = models.CharField(max_length=64, blank=True, verbose_name=_("Record"))

    class Meta:
        verbose_name = _("Website API log")
        verbose_name_plural = _("Website API log")
        ordering = ['-id']
        indexes = [models.Index(fields=['direction', 'created_at'])]

    def __str__(self):
        return f'{self.direction} {self.method} {self.path} → {self.status_code}'

    @classmethod
    def purge(cls, days=90):
        from datetime import timedelta
        deleted, _counts = cls.objects.filter(created_at__lt=timezone.now() - timedelta(days=days)).delete()
        return deleted


# ── a change to the car's options or its new gallery photos is a change too ───
from django.db.models.signals import m2m_changed  # noqa: E402


def _website_car_m2m_changed(sender, instance, action, **kwargs):
    """Many-to-many fields never pass through pre_save, so without this an added
    option or photo left the car "up to date" and was never sent."""
    if action not in ('post_add', 'post_remove', 'post_clear') or not isinstance(instance, WebsiteCar):
        return
    if getattr(instance, '_from_site', False) or not instance.pk or instance.sync_state == 'draft':
        return
    WebsiteCar._base_manager.filter(pk=instance.pk).update(sync_state='pending')
    instance.sync_state = 'pending'
    from car_import.services import website_api
    website_api.schedule_push(instance.pk)


m2m_changed.connect(_website_car_m2m_changed, sender=WebsiteCar.extra_options.through,
                    dispatch_uid='car_import_websitecar_extra_options')
m2m_changed.connect(_website_car_m2m_changed, sender=WebsiteCar.gallery.through,
                    dispatch_uid='car_import_websitecar_gallery')
