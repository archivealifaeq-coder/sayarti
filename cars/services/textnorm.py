# -*- coding: utf-8 -*-
"""نظام التطبيع النصي الموحد لسيارتي.

كل مطابقة في الموقع (البحث، الشرائح، البحث الحر) تمر عبر هذه الدوال
حتى لا تختلف كتابة المستخدم أبداً عن التخزين في قاعدة البيانات:
    أ/إ/آ -> ا     ة -> ه     ى -> ي     إزالة التشكيل والمد
    engine: 2000 == 2.0 == 2L == '2,000'
"""

import re

_HAMZA_MAP = {
    'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
    'ى': 'ي', 'ة': 'ه',
}
_STRIP_RE = re.compile(r'[\u064b-\u065f\u0670\u0640]')  # تشكيل + مد


def fold_ar(text):
    """توحيد النص العربي حسب أحرف اللبس: أ->ا، ة->ه، ى->ي.

    يُطبَّق على قيمة قاعدة البيانات وعلى ما يكتبه المستخدم معاً،
    فمهما كانت الصيغة (اوبل/أوبل/أوبِل) تصبح صيغة واحدة قابلة للمطابقة.
    """
    if not text:
        return ''
    text = str(text).strip().lower()
    out = []
    for ch in text:
        out.append(_HAMZA_MAP.get(ch, ch))
    folded = ''.join(out)
    folded = _STRIP_RE.sub('', folded)
    return folded


def normalize_engine(value):
    """توحيد صيغة حجم المحرك: 2000 -> 2.0، 2L -> 2.0، '2,000' -> 2.0."""
    if not value:
        return value
    value = str(value).strip()

    numbers = re.findall(r'(\d+\.?\d*)', value)
    if numbers:
        num = float(numbers[0])
        if num >= 1000:
            num = num / 1000
        if num == int(num):
            return f"{int(num)}.0"
        return f"{num}"

    return value


def fold_engine(value):
    """صيغة المحرك القابلة للتخزين والبحث عنها ('2.0' دائماً).

    الإدخال بأي صورة (2000 / 2.0 / 2L / 2,000 / 2.0 تيربو) يتحول
    إلى '2.0' ثابتة، والبحث يتم عليها لذا لا يضيع موديل بسبب الصيغة.
    """
    if not value:
        return ''
    norm = normalize_engine(value)
    if norm is None:
        return ''
    folded = str(norm).lower().replace('ل', '').replace('l', '')
    folded = re.sub(r'[^0-9.]', '', folded)
    return folded