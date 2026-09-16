# -*- coding: utf-8 -*-
"""Fill the lawyer's contract, without retyping the lawyer's contract.

The client sent five `.docx` files on 2026-09-16. They are bilingual, sixteen
clauses, and drafted by their lawyer — which settles the design question before
it is asked: we do **not** rebuild this document in HTML. We fill the blanks in
theirs and hand back the same file, with the same wording, the same layout and
the same annexes.

Two things make that harder than a string replace.

**Word splits a sentence across runs.** A paragraph that reads
`السيد/ .......... – مصري الجنسية` can be five `<w:r>` elements, and the dots
can straddle three of them. Replacing text paragraph-by-paragraph would work
and would flatten every bold and underline inside it, which on a contract is
not an acceptable trade. So this walks the runs, maps each character of the
joined paragraph back to the run it came from, and splices the replacement into
only the runs the blank actually covers.

**A blank that fails to fill is worse than no feature at all.** A contract that
goes out with dots where the price should be is a document somebody signs. So
every field is declared required or optional, and `fill()` raises rather than
returning a file when a required one did not land. Nothing half-filled is ever
written to disk.
"""
import io
import re
import zipfile

from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
ET.register_namespace('w', W[1:-1])

#: What a blank looks like in these documents: a run of dots, ellipses, Arabic
#: tatweel or underscores. Three is the shortest that is unambiguously a blank
#: rather than an ellipsis in a sentence.
BLANK = re.compile(r'[.…ـ_·]{3,}')

DOCUMENT = 'word/document.xml'


class ContractFillError(Exception):
    """A contract that cannot be produced safely."""


# ── reading ────────────────────────────────────────────────────────────────
def paragraphs(docx_bytes):
    """Every paragraph's joined text, in document order."""
    root = _root(docx_bytes)
    return [_joined(p) for p in root.iter(W + 'p')]


def blanks_in(docx_bytes):
    """(paragraph index, text, number of blanks) for paragraphs with blanks.

    Used by `import_contract_templates` to show what it is about to tokenise,
    and by anyone auditing a template the client has since edited.
    """
    out = []
    for index, text in enumerate(paragraphs(docx_bytes)):
        count = len(BLANK.findall(text))
        if count:
            out.append((index, text, count))
    return out


# ── writing ────────────────────────────────────────────────────────────────
def tokenise(docx_bytes, rules):
    """Turn blanks into named tokens, so the file becomes a template.

    `rules` is a list of `(anchor, [token_or_None, ...])`. The anchor is a
    distinctive substring of the paragraph — a clause's own words — and the
    list says what each blank in that paragraph becomes, in order. `None`
    leaves a blank alone, which is how a signature line stays a signature line.
    """
    root = _root(docx_bytes)
    paras = list(root.iter(W + 'p'))
    applied, missing = 0, []

    for anchor, tokens in rules:
        # The first paragraph that contains the anchor AND has a blank in it.
        # Requiring the blank is not a refinement, it is the whole point: the
        # phrase "بطاقة رقم قومي /" appears first in the clause naming the
        # COMPANY's own signatory, where the number is already printed. Taking
        # the first textual match there would silently leave the customer's
        # clause — the one with the blanks — untouched, and the contract would
        # go out with dots where the customer's ID belongs.
        target = next((p for p in paras
                       if anchor in _joined(p) and BLANK.search(_joined(p))), None)
        if target is None:
            missing.append(anchor)
            continue
        replacements = []
        for match, token in zip(BLANK.finditer(_joined(target)), tokens):
            if token is None:
                continue
            replacements.append((match.start(), match.end(), '{{%s}}' % token))
        if replacements:
            _splice(target, replacements)
            applied += 1

    return _write(root, docx_bytes), applied, missing


def fill(docx_bytes, values, required=()):
    """Replace `{{token}}` with a value everywhere, or refuse.

    Refusing is the point. A contract with dots where the price should be is a
    document somebody signs, so a required token that did not land raises
    instead of returning a file.
    """
    root = _root(docx_bytes)
    for paragraph in root.iter(W + 'p'):
        text = _joined(paragraph)
        if '{{' not in text:
            continue
        replacements = []
        for match in re.finditer(r'\{\{(\w+)\}\}', text):
            token = match.group(1)
            if token in values:
                replacements.append((match.start(), match.end(), str(values[token])))
        if replacements:
            _splice(paragraph, replacements)

    result = _write(root, docx_bytes)
    leftover = sorted({t for t in re.findall(r'\{\{(\w+)\}\}', ' '.join(paragraphs(result)))})
    unfilled = [t for t in leftover if t in required]
    if unfilled:
        raise ContractFillError(
            'These fields are still empty and the contract was not produced: '
            + ', '.join(unfilled))
    return result, leftover


# ── the run-splicing that makes the above safe ─────────────────────────────
#: Every `xmlns:prefix="uri"` on the document element.
_XMLNS = re.compile(r'xmlns:([\w.-]+)\s*=\s*"([^"]+)"')


def _register_prefixes(xml_text):
    """Keep Word's own namespace prefixes, or Word calls the file corrupt.

    ElementTree renames unregistered namespaces to ns0, ns1, ns2 on output.
    That would be harmless except that a .docx carries
    `mc:Ignorable="w14 w15 w16se … wp14"` — an attribute whose VALUE is a list
    of prefixes. Rename the declarations and that list points at prefixes the
    document no longer declares, which is a validation error: Word refuses to
    open the file and offers to repair it.

    So every prefix on the original document element is re-registered before
    anything is written back. Registration is global to ElementTree, which is
    fine — these are the standard OOXML namespaces, and re-registering the same
    prefix for the same URI is a no-op.
    """
    # NOT "up to the first '>'": a .docx opens with an XML declaration, so the
    # first '>' closes `<?xml … ?>` and the document element's declarations sit
    # after it. The first few kilobytes cover the root element on every real
    # file, and a stray extra registration would be harmless anyway.
    for prefix, uri in _XMLNS.findall(xml_text[:8000]):
        ET.register_namespace(prefix, uri)


def _root(docx_bytes):
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        raw = z.read(DOCUMENT)
    _register_prefixes(raw.decode('utf-8', 'replace'))
    return ET.fromstring(raw)


def _write(root, original_bytes):
    """A new .docx: the original archive with one part swapped.

    Everything else — styles, fonts, images, the bilingual table — is copied
    byte for byte. We are editing a lawyer's document, not regenerating it.
    """
    body = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    body = _restore_root_tag(body, original_bytes)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original_bytes)) as src, \
            zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = body if item.filename == DOCUMENT else src.read(item.filename)
            dst.writestr(item, data)
    return out.getvalue()


def _restore_root_tag(new_xml, original_bytes):
    """Put back the document element exactly as Word wrote it.

    ElementTree only re-emits the namespaces the tree actually uses, so a
    declaration like `xmlns:w15=…` disappears when nothing in this document
    happens to use it — while `mc:Ignorable="w14 w15 w16se … wp14"` goes on
    naming it. An Ignorable entry with no matching declaration is a validation
    error, and Word answers validation errors on a .docx by announcing the file
    is corrupt and offering to repair it. On a signed contract that is not a
    cosmetic problem.

    Swapping the whole start tag back is cheap and total: the body we generated
    is unchanged, and the root is byte-identical to the lawyer's.
    """
    with zipfile.ZipFile(io.BytesIO(original_bytes)) as z:
        original = z.read(DOCUMENT)
    old_start, old_end = _root_tag_span(original)
    new_start, new_end = _root_tag_span(new_xml)
    if old_start < 0 or new_start < 0:
        return new_xml
    return new_xml[:new_start] + original[old_start:old_end] + new_xml[new_end:]


def _root_tag_span(xml_bytes):
    """(start, end) of the document element's start tag, skipping the prolog."""
    cursor = 0
    while True:
        start = xml_bytes.find(b'<', cursor)
        if start < 0:
            return -1, -1
        if xml_bytes[start + 1:start + 2] in (b'?', b'!'):
            cursor = xml_bytes.find(b'>', start) + 1
            continue
        end = xml_bytes.find(b'>', start)
        return (start, end + 1) if end >= 0 else (-1, -1)


def _text_nodes(paragraph):
    """Every `<w:t>` in this paragraph, in order, skipping deleted revisions."""
    return [node for node in paragraph.iter(W + 't')]


def _joined(paragraph):
    return ''.join(node.text or '' for node in _text_nodes(paragraph))


def _splice(paragraph, replacements):
    """Apply (start, end, text) spans to a paragraph, preserving its runs.

    Works backwards so earlier offsets stay valid, and writes the replacement
    into the FIRST run the span touches while clearing the rest of the span
    from the others. Formatting outside the span is untouched — which is the
    whole reason this is not a paragraph-level string replace.
    """
    nodes = _text_nodes(paragraph)
    spans, cursor = [], 0
    for node in nodes:
        length = len(node.text or '')
        spans.append((cursor, cursor + length, node))
        cursor += length

    for start, end, text in sorted(replacements, reverse=True):
        written = False
        for node_start, node_end, node in spans:
            if node_end <= start or node_start >= end:
                continue
            value = node.text or ''
            head = value[:max(0, start - node_start)]
            tail = value[max(0, end - node_start):] if end <= node_end else ''
            if not written:
                node.text = head + text + tail
                written = True
            else:
                node.text = head + tail


def fill_table_row(docx_bytes, first_cell_text, cell_tokens):
    """Put a token into the empty cells of a table row, by its label.

    Annex 1's payment schedule has a `Date` row full of dotted blanks and an
    `Amount` row that is simply empty — nothing to find and replace. So this
    locates the row by what its first cell says and writes into the rest.
    """
    root = _root(docx_bytes)
    for row in root.iter(W + 'tr'):
        cells = list(row.iter(W + 'tc'))
        if not cells:
            continue
        label = ''.join(_joined(p) for p in cells[0].iter(W + 'p')).strip()
        if label != first_cell_text:
            continue
        for cell, token in zip(cells[1:], cell_tokens):
            if token is None:
                continue
            paras = list(cell.iter(W + 'p'))
            if not paras:
                continue
            nodes = _text_nodes(paras[0])
            if nodes:
                nodes[0].text = '{{%s}}' % token
                for node in nodes[1:]:
                    node.text = ''
            else:
                # An empty cell has no run at all; give it one.
                run = ET.SubElement(paras[0], W + 'r')
                node = ET.SubElement(run, W + 't')
                node.text = '{{%s}}' % token
                node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        return _write(root, docx_bytes)
    return docx_bytes


def replace_literals(docx_bytes, rules):
    """Swap fixed text for a token inside anchored paragraphs only.

    The contract hard-codes its own year — and the Arabic half says 2026 while
    the English half says 2025, in the same document. Anchoring the swap keeps
    a stray "2026" elsewhere in the text from being rewritten too.
    """
    root = _root(docx_bytes)
    paras = list(root.iter(W + 'p'))
    for anchor, pairs in rules:
        for paragraph in paras:
            text = _joined(paragraph)
            if anchor not in text:
                continue
            replacements = []
            for old, token in pairs:
                for match in re.finditer(re.escape(old), text):
                    replacements.append((match.start(), match.end(), '{{%s}}' % token))
            if replacements:
                _splice(paragraph, replacements)
            break
    return _write(root, docx_bytes)


def repeat_rule(docx_bytes, exact_text, tokens):
    """Tokenise several identical paragraphs — the annex's three date cells.

    They carry the same text, so no anchor can tell them apart; order is the
    only thing that distinguishes them, and order is exactly what the payment
    schedule means.
    """
    root = _root(docx_bytes)
    seen = 0
    for paragraph in root.iter(W + 'p'):
        if _joined(paragraph).strip() != exact_text.strip():
            continue
        if seen >= len(tokens):
            break
        token = tokens[seen]
        seen += 1
        if token is None:
            continue
        # The whole paragraph, not "from the first blank onwards". The annex
        # line reads `…… / …….. / 2026`, and its FIRST group is only two
        # ellipsis characters — below the three that make a blank — so
        # starting at the first match left `…… / ` stranded in front of the
        # date. The line is nothing but a placeholder, so it is replaced whole.
        text = _joined(paragraph)
        _splice(paragraph, [(0, len(text), '{{%s}}' % token)])
    return _write(root, docx_bytes)
