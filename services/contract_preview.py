# -*- coding: utf-8 -*-
"""The contract before the money, and the office for a contract that must change.

Two of the owner's rules of 2026-09-30.

**A customer may read the contract before paying.** «ممكن العميل يطلب نسخه من
العقد يتطلع عليها ف ملازم نقوله ادفع الاول عشان نوريك العقد … العقد يتبعت من
غير اختام او امضاء وكدا مجرد نسخه فاضيه فيه بنود العقد، لما يسأل بس.» So this
takes the lawyer's own template for the customer's programme, empties every
field — no name, figure or date — strips every picture (a stamp or a signature
is a picture in these files), and sends it only when asked.

**A signed contract is changed in person.** The customer is invited to the
company's office. The wording is a switch management edits in
الإعدادات ← مفاتيح التشغيل, and the map link is a switch of its own: the owner
has not sent one yet, and a placeholder must never reach a customer.
"""
import hashlib
import logging
import re

logger = logging.getLogger(__name__)

#: What an emptied field reads as: a line to write on, like the lawyer's own blanks.
BLANK = '..............'
#: Bumped when the emptying changes, so a stored copy is rebuilt once.
VERSION = b'blank-copy-1'

OFFICE_TEXT_KEY = 'car_import.office_visit_text'
OFFICE_MAP_KEY = 'car_import.office_map_link'
DEFAULT_OFFICE_TEXT = ('لو حضرتك محتاج أي تعديل في العقد، يسعدنا نستقبلك في مقر الشركة ونراجعه مع حضرتك:\n'
                       '📍 مجمع البنوك – أسفل بنك CIB – التجمع الخامس، القاهرة الجديدة\n'
                       'New Cairo – Banks Complex, below CIB Bank')

PROGRAMME_AR = {'initiative': 'المبادرة', 'personal': 'الاستيراد الشخصي', 'commercial': 'الاستيراد التجاري'}


def _param(key):
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=key).values('value').first()
    except Exception:
        return ''
    return str((row or {}).get('value') or '').strip()


def office_visit_text():
    """The invitation, with the map link once management has pasted one."""
    text = _param(OFFICE_TEXT_KEY) or DEFAULT_OFFICE_TEXT
    link = _param(OFFICE_MAP_KEY)
    if link and link not in text:
        text += f'\n🗺️ اللوكيشن: {link}'
    return text


def template_for(programme):
    """The fill-in master for the programme, as a contract draft would pick it."""
    from django.db.models import Q

    from car_import.models import ContractTemplate
    return (ContractTemplate.objects.filter(is_fillable=True)
            .filter(Q(program=programme) | Q(program='any'))
            .order_by('program').first())


def _source(template):
    template.docx.open('rb')
    try:
        return template.docx.read()
    finally:
        template.docx.close()


def _without_pictures(docx_bytes):
    """The document without drawings or embedded objects — the stamps and
    signatures, and any other picture with them."""
    from car_import.services import contract_docx

    W = contract_docx.W
    pictures = {W + 'drawing', W + 'pict', W + 'object'}
    root = contract_docx._root(docx_bytes)
    removed = 0
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag in pictures:
                parent.remove(child)
                removed += 1
    return contract_docx._write(root, docx_bytes) if removed else docx_bytes


def blank_bytes(template):
    """The template with every {{field}} emptied and no pictures."""
    from car_import.services import contract_docx

    source = _source(template)
    tokens = sorted(set(re.findall(r'\{\{(\w+)\}\}', ' '.join(contract_docx.paragraphs(source)))))
    emptied, _leftover = contract_docx.fill(source, {token: BLANK for token in tokens})
    return _without_pictures(emptied)


class _StoredFile:
    """Just what `sales_flow.send_document` reads off a file field."""

    def __init__(self, name):
        from django.core.files.storage import default_storage
        self.name = name
        self.url = default_storage.url(name)


def blank_copy(programme):
    """(file, '') ready to send, or (None, why). Built once per template version."""
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    template = template_for(programme)
    if template is None or not template.docx:
        return None, f'no contract template for programme {programme!r}'
    digest = hashlib.sha1(_source(template) + VERSION).hexdigest()[:10]
    path = f'car_import/contract_previews/Khaled-Automobile-contract-{programme}-{digest}.docx'
    if not default_storage.exists(path):
        path = default_storage.save(path, ContentFile(blank_bytes(template)))
    return _StoredFile(path), ''


def programme_of(partner, explicit=None):
    """The customer's programme: what the assistant passed, else the open deal's,
    else the latest quotation's, else the lead's."""
    if explicit in PROGRAMME_AR:
        return explicit
    from car_import.services import sales_flow
    from car_import.services.chat_actions import lead_for, open_deal_for
    deal = open_deal_for(partner)
    if deal is not None and getattr(deal, 'program', None) in PROGRAMME_AR:
        return deal.program
    quote = sales_flow.latest_open_quote(partner)
    if quote is not None and quote.programme in PROGRAMME_AR:
        return quote.programme
    lead = lead_for(partner)
    program = getattr(lead, 'ka_program', None) if lead is not None else None
    return program if program in PROGRAMME_AR else None
