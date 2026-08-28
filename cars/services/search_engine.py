# -*- coding: utf-8 -*-
"""محرك التفسير للنص الحر (البحث السريع).

يحوّل عبارة المستخدم مثل "سونيته 2008" أو "سونت 2008" إلى تفسير
(ماركة، موديل، سنة) بدرجة ثقة، ليُعرض للمستخدم كـ "هل تقصد" قبل
التنفيذ. كل المطابقة تمر بالتطبيع الموحد (textnorm.fold_ar) ومسافة
التحرير (Levenshtein) لتغطية الأخطاء الشائعة بدون قاموس ثابت.
"""

from itertools import product
from django.db.models import Count
from cars.services.textnorm import fold_ar, fold_engine


def _edit_distance(a, b):
    """مسافة التحرير Levenshtein (عمودان فقط لتوفير الذاكرة)."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def _word_score(word, name):
    """درجة تطابق كلمة بمفردها مع اسم (ماركة/موديل).

    6 = مطابقة تامة، 5 = احتواء متبادل، 4 = بادئة أو مسافة 1،
    3 = مسافة 2، 2 = مسافة 3، وإلا 0.
    """
    if not word or not name:
        return 0
    if word == name:
        return 6
    if word in name or name in word:
        return 5
    if len(word) >= 2 and len(name) >= 2:
        if word.startswith(name) or name.startswith(word):
            return 4
    d = _edit_distance(word, name)
    if d <= 1:
        return 4
    if d <= 2:
        return 3
    if d <= 3:
        return 2
    return 0


def _best_word(words, names):
    """أفضل (كلمة، اسم، درجة) عبر كل الكلمات وكل الأسماء."""
    best = (None, None, 0)
    for w, n in product(words, names):
        s = _word_score(w, n)
        if s > best[2]:
            best = (w, n, s)
    return best


def _car_count(brand_ar='', model_ar='', year=None):
    from cars.models import CarSpecification
    qs = CarSpecification.objects.all()
    if brand_ar:
        b = fold_ar(brand_ar)
        qs = qs.filter(brand_norm__icontains=b)
    if model_ar:
        m = fold_ar(model_ar)
        qs = qs.filter(model_norm__icontains=m)
    if year:
        qs = qs.filter(year=int(year))
    return qs.count()


def find_interpretation(q, top=3):
    """يعيد قائمة تفسيرات مرتّبة للمصطلح الحر q.

    كل تفسير: {brand_ar, brand_en, model_ar, model_en, year,
               corrected, count}.
    """
    from cars.models import CarSpecification

    q = (q or '').strip()
    if not q:
        return []

    tokens = q.split()
    year = None
    words = []
    for t in tokens:
        if t.isdigit() and 1900 <= int(t) <= 2099 and len(t) == 4:
            year = int(t)
        else:
            f = fold_ar(t)
            if f:
                words.append(f)

    brands = list(CarSpecification.objects.values('brand_ar', 'brand_en')
                  .annotate(bc=Count('id')).order_by('-bc')[:80])
    brand_folded = {b['brand_ar']: fold_ar(b['brand_ar']) for b in brands}

    w, chosen_brand, bs = _best_word(words, [fold_ar(b) for b in brand_folded])
    brand_ar = chosen_brand if bs >= 4 else None
    brand_en = next((b['brand_en'] for b in brands if b['brand_ar'] == brand_ar), '') if brand_ar else ''

    remaining = [x for x in words if x != (fold_ar(w) if w else '')] if brand_ar else list(words)

    models_meta = []
    model_ar = None
    model_en = ''
    ms = 0
    if brand_ar:
        model_pairs = list(CarSpecification.objects.filter(
            brand_norm__icontains=fold_ar(brand_ar)
        ).values_list('model_ar', 'model_en').distinct().order_by('model_ar')[:200])
        if remaining:
            w2, m, ms = _best_word(remaining, [fold_ar(r[0]) for r in model_pairs])
            if ms >= 3:
                model_ar = m
                model_en = next((r[1] for r in model_pairs if fold_ar(r[0]) == m), '')
        models_meta = model_pairs
        # إن لم يطابق أي كلمة موديلاً، جرب كل الكلمات المتبقية كتطابق جزئي
        if not model_ar and remaining:
            joined = ''.join(remaining)
            for pair in model_pairs:
                s = _word_score(joined, fold_ar(pair[0]))
                if s > ms:
                    ms = s
                    model_ar = fold_ar(pair[0]).strip()
                    model_en = pair[1]

    exact = True
    matched_word = fold_ar(w) if w else ''
    if brand_ar and bs < 6:
        exact = False
    if model_ar and ms < 6:
        exact = False
    corrected = not exact

    count = _car_count(brand_ar or '', model_ar or '', year)

    interpretations = []
    if brand_ar or model_ar:
        interpretations.append({
            'brand_ar': brand_ar or '',
            'brand_en': brand_en,
            'model_ar': model_ar or '',
            'model_en': model_en,
            'year': year,
            'corrected': corrected,
            'count': count,
        })

    # بدائل: الموديل المعروف كتفسير مستقل حتى لو كانت الماركة مجهولة
    alt_names = []
    if not model_ar and remaining:
        pairs_all = list(CarSpecification.objects.values_list(
            'model_ar', 'model_en').distinct().order_by('model_ar')[:200])
        w3, m3, s3 = _best_word(remaining, [fold_ar(r[0]) for r in pairs_all])
        if s3 >= 3 and m3:
            alt_names.append((m3, next((r[1] for r in pairs_all if fold_ar(r[0]) == m3), '')))

    for m3, m3en in alt_names:
        cnt = _car_count('', m3, year)
        if not any(i['model_ar'] == m3 for i in interpretations):
            interpretations.append({
                'brand_ar': '', 'brand_en': '',
                'model_ar': m3, 'model_en': m3en,
                'year': year, 'corrected': True, 'count': cnt,
            })

    interpretations.sort(key=lambda i: (i['count'] if i['count'] > 0 else -1, i['corrected']), reverse=True)
    return interpretations[:top]


def interpretation_url(item):
    """يبني رابط البحث الدقيق من تفسير."""
    params = []
    if item.get('brand_ar'):
        params.append('brand=' + item['brand_ar'])
    if item.get('model_ar'):
        params.append('model=' + item['model_ar'])
    if item.get('year'):
        params.append('year=%d' % item['year'])
    return '/?' + '&'.join(params) if params else '/'