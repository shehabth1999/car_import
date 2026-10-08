# -*- coding: utf-8 -*-
"""Every contract a customer receives goes as a PDF.

The owner, 2026-10-07: «العقود الدرافت كلها تتبعت PDF». The lawyer's templates
are Word files and stay Word files — that is what management edits — but a
customer on a phone often cannot open a .docx: the client's own test customer
wrote «ممكن نسخه Pdf عشان ده مش شغال», and the assistant sent the same Word
file again and called it a PDF.

The conversion is LibreOffice, headless, on the server (`soffice`): it is the
only converter that reads these files faithfully — two columns, Arabic beside
English, the annex tables. A server without it still sends the Word file
rather than nothing, and says so to whoever called.

The PDF is stored next to its .docx (same name, `.pdf`) and built once: a
contract or a blank copy that is sent twice is converted once.
"""
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

#: A seven-page contract converts in about two seconds; a first run on a cold
#: server takes longer while LibreOffice builds its profile.
TIMEOUT_SECONDS = 120


class StoredFile:
    """Just what `sales_flow.send_document` reads off a file field."""

    def __init__(self, name):
        from django.core.files.storage import default_storage
        self.name = name
        self.url = default_storage.url(name)


def converter():
    """The LibreOffice binary, or None on a server without it."""
    return shutil.which('soffice') or shutil.which('libreoffice')


def docx_to_pdf(docx_bytes):
    """(pdf bytes, '') or (None, why)."""
    binary = converter()
    if not binary:
        return None, 'LibreOffice (soffice) is not installed on this server'
    with tempfile.TemporaryDirectory(prefix='ka-contract-') as folder:
        source = os.path.join(folder, 'contract.docx')
        with open(source, 'wb') as handle:
            handle.write(docx_bytes)
        # A profile of its own: two workers converting at the same moment
        # must not lock each other out of a shared one.
        profile = 'file://' + os.path.join(folder, 'profile')
        try:
            subprocess.run(
                [binary, f'-env:UserInstallation={profile}', '--headless', '--norestore',
                 '--convert-to', 'pdf', '--outdir', folder, source],
                check=True, timeout=TIMEOUT_SECONDS, capture_output=True)
        except (subprocess.SubprocessError, OSError) as exc:
            logger.exception('car_import: the contract could not be converted to PDF')
            return None, f'the PDF conversion failed: {exc}'
        target = os.path.join(folder, 'contract.pdf')
        if not os.path.exists(target):
            return None, 'the PDF conversion produced no file'
        with open(target, 'rb') as handle:
            return handle.read(), ''


def pdf_of(docx_name):
    """(file to send, '') for a stored .docx — its PDF, made once — or
    (the .docx itself, why) when no PDF can be made."""
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    root, extension = os.path.splitext(docx_name)
    if extension.lower() != '.docx':
        return StoredFile(docx_name), ''
    pdf_name = f'{root}.pdf'
    if default_storage.exists(pdf_name):
        return StoredFile(pdf_name), ''
    with default_storage.open(docx_name, 'rb') as handle:
        source = handle.read()
    pdf, why = docx_to_pdf(source)
    if pdf is None:
        return StoredFile(docx_name), why
    # `save` may rename on a clash; what it returns is the name that exists.
    return StoredFile(default_storage.save(pdf_name, ContentFile(pdf))), ''
