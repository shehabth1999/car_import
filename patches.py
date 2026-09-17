# -*- coding: utf-8 -*-
"""car_import runtime patches, applied from apps.ready().

One patch, and the reason it is a patch rather than configuration is worth
stating: AI Studio has **no hook between the agent's reply and the channel
send**. No signal, no `pre_send`, no `global_configuration` key, no settings
callable — the five channel bridges each call `execute_workflow_sync`, read
`result.output`, and send it. So the outbound gate the plan calls agent A10
has nowhere to stand except in front of that one function.

It can stand there because every bridge imports it **lazily, inside the task
body**, by attribute from the package `modules.aistudio.services`
(`aistudio_whatsapp/tasks.py:100`, `_messenger:111`, `_instagram:111`,
`_tiktok:105`, `_webbot:116`, `aistudio/utils/followup_send.py:154`).
Rebinding the package attribute intercepts all six with one assignment. A
patch on the defining module (`services.workflow_executor`) would intercept
none of them.

The wrapper only ever touches workflows of ours — it reads the workflow name
and leaves every other tenant's graph alone, in case this code is ever shared.
"""
import logging

logger = logging.getLogger(__name__)

_PATCHED = False

#: Only replies from these workflows are gated. The prefix is what
#: `ka_sales_definition.workflow_payload()` names them.
OUR_WORKFLOW_PREFIX = 'KA Sales'


def apply_patches():
    global _PATCHED
    if _PATCHED:
        return
    try:
        from modules.aistudio import services as aistudio_services
    except Exception:  # pragma: no cover - aistudio not installed on this tenant
        logger.warning('car_import: aistudio is not installed; the outbound gate is off')
        return

    original = aistudio_services.execute_workflow_sync

    def execute_workflow_sync(workflow_id, input_data, **kwargs):
        from django.utils import timezone

        started = timezone.now()
        result = original(workflow_id, input_data, **kwargs)
        try:
            return _gate(result, workflow_id, kwargs, started)
        except Exception:
            # The gate must never be the reason a customer hears nothing. If
            # it breaks, the reply goes out as the engine produced it, and the
            # traceback goes to the log where somebody will see it.
            logger.exception('car_import: the outbound gate failed open')
            return result

    execute_workflow_sync.__wrapped__ = original
    aistudio_services.execute_workflow_sync = execute_workflow_sync
    _PATCHED = True
    logger.info('car_import: outbound gate installed in front of execute_workflow_sync')


def _gate(result, workflow_id, kwargs, started):
    import dataclasses

    text = getattr(result, 'output', None)
    if not isinstance(text, str) or not text.strip():
        return result                       # nothing to inspect: empty, dict, interrupt
    if not getattr(result, 'success', False):
        return result                       # a failure is the bridge's to handle

    name = _workflow_name(workflow_id)
    if not name.startswith(OUR_WORKFLOW_PREFIX):
        return result

    from car_import.services import supervisor

    conversation = kwargs.get('conversation')
    replacement, problems = supervisor.gate(text, conversation=conversation,
                                            since=started, workflow_name=name)
    if problems:
        logger.info('car_import: gate on "%s" — %s', name,
                    '; '.join(f"{p['severity']}:{p['rule']}" for p in problems))
    if replacement == text:
        return result
    # A blocked reply hands the conversation over; the bridge must still send
    # the holding sentence even though `handled_by_ai` is now False. That is
    # exactly what `escalated_this_run` exists for (workflow_executor.py:80).
    return dataclasses.replace(result, output=replacement, escalated_this_run=True)


def _workflow_name(workflow_id):
    try:
        from modules.aistudio.models import WorkflowDefinition
        return (WorkflowDefinition.objects.filter(pk=workflow_id)
                .values_list('name', flat=True).first() or '')
    except Exception:
        return ''


# ── the extension's own pages ─────────────────────────────────────────────────
def apply_url_patches():
    """Mount `car_import/urls.py` into the root urlconf, without touching core.

    Core mounts modules by name in `project/urls.py`; an extension has no
    line there. Django builds its resolver lazily from the urlconf module's
    `urlpatterns` — a plain list — so inserting our `include()` at startup,
    before the website catch-all, is all a route needs. Idempotent, and it
    clears the resolver cache in case something resolved a URL already.
    """
    import importlib

    try:
        from django.conf import settings
        from django.urls import clear_url_caches, include, path

        root = importlib.import_module(settings.ROOT_URLCONF)
        patterns = getattr(root, 'urlpatterns', None)
        if patterns is None:
            return
        for entry in patterns:
            if getattr(entry, 'namespace', None) == 'car_import':
                return
        mount = path('', include(('car_import.urls', 'car_import'), namespace='car_import'))
        index = len(patterns)
        for i, entry in enumerate(patterns):
            target = getattr(getattr(entry, 'urlconf_name', None), '__name__', '')
            if target == 'modules.genie.website_urls':   # the catch-all must stay last
                index = i
                break
        patterns.insert(index, mount)
        clear_url_caches()
        logger.info("car_import: pages mounted at /car-import/ (index %s of %s)", index, len(patterns))
    except Exception:  # noqa: BLE001 — a page that fails to mount must not take the app down
        logger.exception("car_import: could not mount the extension's urls")
