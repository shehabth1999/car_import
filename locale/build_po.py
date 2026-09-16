# -*- coding: utf-8 -*-
"""Write the Arabic `.po` from `ar_catalog.py`.

    python locale/build_po.py                # fills locale/ar/LC_MESSAGES/django.po in place

`collect_translations` writes one entry per (source file, string), so the same
label appears many times with different `msgctxt`. The catalog is keyed on the
string alone — a label means the same thing on every screen — and this fills
every context from it. Strings that are already Arabic in the source are
their own translation. Anything the catalog does not know is listed at the
end, so a new English string cannot slip into production untranslated without
somebody seeing its name.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ar_catalog import CATALOG  # noqa: E402

PO = os.path.join(HERE, 'ar', 'LC_MESSAGES', 'django.po')

MANIFEST_DESCRIPTION = (
    "\nاستيراد العربيات (خالد أوتوموبيل GmbH + K&T)\n"
    "-----------------------------------------\n"
    "الصفقة سجل مستقل، مش أمر بيع — موديولات `sales` و`account` و`payment`\n"
    "و`products` لا تُركّب أبداً (القرار D24).\n\n"
    "- CarDeal: عربية واحدة، عميل واحد، مراحل الشحن الـ13 بتاعة العميل، علامة مدفوع/غير مدفوع\n"
    "  بيحطها إنسان، شروط التمويل، مبالغ العقد وبيانات الشحن.\n"
    "- ImportStage: المراحل ورسالة العميل لكل مرحلة، بتتعدّل من التشغيل.\n"
    "- StageChangeLog: صف لكل انتقال، مع نتيجة الرسالة.\n"
    "- كل نقلة مرحلة بتبعت للعميل رسالة تلقائية على القناة اللي بيستخدمها\n"
    "  (كل المراحل ما عدا الإلغاء).\n"
)

ARABIC = re.compile('[\u0600-\u06ff]')


def unescape(value):
    return value.encode('utf-8').decode('unicode_escape').encode('latin-1').decode('utf-8')


def escape(value):
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def main():
    text = open(PO, encoding='utf-8').read()
    out, missing, filled = [], [], 0
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r'^msgid "(.*)"$', line)
        if match and i + 1 < len(lines) and lines[i + 1].startswith('msgstr '):
            raw = match.group(1)
            msgid = unescape(raw)
            out.append(line)
            if msgid == '':
                out.append(lines[i + 1])               # the header entry
                i += 2
                continue
            translation = CATALOG.get(msgid)
            if translation is None and ARABIC.search(msgid) and not re.search(r'[A-Za-z]{3,}', msgid):
                translation = msgid                    # already Arabic
            if translation is None and msgid.lstrip().startswith('Car Import (Khaled Automobile GmbH'):
                # The manifest's description — one multi-line paragraph shown
                # in the module installer. Matched by prefix so a rewrapped
                # docstring does not silently drop it from the catalog.
                translation = MANIFEST_DESCRIPTION
            if translation is None:
                missing.append(msgid)
                out.append('msgstr ""')
            else:
                out.append('msgstr "%s"' % escape(translation))
                filled += 1
            i += 2
            continue
        out.append(line)
        i += 1

    open(PO, 'w', encoding='utf-8').write('\n'.join(out))
    print('filled %d entries' % filled)
    if missing:
        uniq = sorted(set(missing))
        print('NOT in the catalog (%d):' % len(uniq))
        for m in uniq:
            print('  ', m[:110])
        sys.exit(1)
    print('every entry translated')


if __name__ == '__main__':
    main()
