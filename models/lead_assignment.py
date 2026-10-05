# -*- coding: utf-8 -*-
"""Who gets the next lead.

The client's Odoo hands every new lead to a salesperson by tag, in turn, with a
daily cap — a small custom module (`crm.assignment.group`) holding three groups
today: nine tags shared by six salespeople, and two one-tag groups with one
person each. This is the same table, field for field, so management sets it up
the way they already know.

Two objects, because they answer two different questions:

* **`LeadAssignmentGroup`** — the rule. Which tags, which salespeople, how many
  a day, and whose turn it is.
* **`LeadAssignmentLog`** — one row per lead the job handed out. It exists to be
  counted: "how many did this person get from this group today" has to be a
  query, not a guess from the lead's own salesperson, which anybody can change
  by hand a minute later.

Nothing here assigns anything. The job that reads these tables is
`services/lead_assignment.py`.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel


class LeadAssignmentGroup(BaseModel):
    """One rule: leads with these tags go to these salespeople, in turn."""

    name = models.CharField(max_length=128, verbose_name=_("Name"))
    # No tags is a rule of its own — the catch-all, tried after every group that
    # has tags. Odoo had no such thing; without it a lead nobody tagged (which is
    # every lead the channels create here) would never be handed to anyone.
    tags = models.ManyToManyField(
        'crm.Tag', blank=True, related_name='+', verbose_name=_("Lead tags"),
        help_text=_("A lead that carries any of these tags belongs to this group. Leave empty to make this a catch-all group: it is tried last and takes the leads no tagged group matched."))
    salespeople = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='+',
                                         verbose_name=_("Salespeople"))
    daily_limit = models.PositiveIntegerField(
        default=100, verbose_name=_("Daily limit"),
        help_text=_("The most leads one salesperson receives from this group in a day. 0 means no limit."))
    #: The place, in the group's salespeople ordered by id, of whoever received
    #: the last lead; the search for the next one starts right after it. Empty
    #: until the first lead. The job owns it — a person editing a turn counter
    #: is a person deciding who gets the next lead.
    last_assigned_index = models.PositiveIntegerField(null=True, blank=True, editable=False,
                                                      verbose_name=_("Last turn"))

    class Meta:
        verbose_name = _("Lead assignment group")
        verbose_name_plural = _("Lead assignment groups")
        # The order the job tries them in, so the list reads as the priority.
        ordering = ['id']

    def __str__(self):
        return self.name


class LeadAssignmentLog(BaseModel):
    """One lead the job handed out: from which group, to whom. `created_at` is when."""

    group = models.ForeignKey(LeadAssignmentGroup, on_delete=models.CASCADE, related_name='assignments',
                              verbose_name=_("Group"))
    lead = models.ForeignKey('crm.Lead', on_delete=models.CASCADE, related_name='+',
                             verbose_name=_("Lead"))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+',
                             verbose_name=_("Salesperson"))

    class Meta:
        verbose_name = _("Lead assignment log")
        verbose_name_plural = _("Lead assignment log")
        ordering = ['-id']
        # The daily count: this group, this person, since midnight.
        indexes = [models.Index(fields=['group', 'user', 'created_at'], name='ka_lead_assign_day_idx')]

    def __str__(self):
        return f'{self.group} → {self.user}'
