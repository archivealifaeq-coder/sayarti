import json
import logging
import requests
from django.conf import settings
from ..models import SiteSettings

logger = logging.getLogger('cars')

DEEPSEEK_API_URL = 'https://api.deepseek.com/chat/completions'
MODEL = 'deepseek-chat'
TIMEOUT = 30


def get_api_key():
    try:
        key = SiteSettings.load().deepseek_api_key
        if key:
            return key
    except Exception:
        pass
    return getattr(settings, 'DEEPSEEK_API_KEY', '')

BUDGET_PROMPT = """أنت خبير سوق السيارات العراقية. أعطني اقتراحات سيارات مناسبة للميزانية المحددة.

الميزانية: {budget} {currency_name}
نوع السيارة: {car_type}
الحالة: {condition}

أعطني 6-8 سيارات مناسبة بالسوق العراقي بالتنسيق التالي (JSON فقط، بدون نص إضافي):
[
  {{
    "name": "اسم السيارة والموديل",
    "year": 2018,
    "price_iq": "20-25 مليون",
    "price_usd": "13,000-16,000",
    "engine": "1.6L",
    "fuel_economy": "ممتاز/جيد/مقبول",
    "maintenance": "رخيصة/متوسطة/غالية",
    "pros": "مميزات مختصرة"
  }}
]

قواعد:
1. الأسعار بالدينار العراقي والدولار
2. فقط سيارات متوفرة فعلياً بالعراق
3. اذكرอมوشام العل-brand المتوفرة: تويوتا، هيونداي، كيا، نيسان، مازدا، شيري، MG، جيلي
4. لا تتجاوز الميزانية
5. أضف ملاحظة: "الأسعار تقريبية وتختلف حسب الحالة والكيلومتر"
6. JSON فقط بدون أي نص قبل أو بعد"""


def find_cars_by_budget(budget, currency='iqd', car_type='all', condition='used'):
    api_key = get_api_key()
    if not api_key:
        return {'success': False, 'error': 'خدمة الذكاء الاصطناعي غير مفعلة حالياً'}

    currency_names = {
        'iqd': 'دينار عراقي',
        'usd': 'دولار أمريكي',
    }
    car_type_names = {
        'all': 'أي نوع',
        'japanese': 'ياباني (تويوتا، نيسان، مازدا)',
        'korean': 'كوري (هيونداي، كيا)',
        'chinese': 'صيني (شيري، MG، جيلي)',
        'american': 'أمريكي (شفروليت، فورد)',
        'european': 'أوروبي (فولكس، أوبل)',
    }
    condition_names = {
        'used': 'مستعمل',
        'new': 'جديد',
    }

    prompt = BUDGET_PROMPT.format(
        budget=f'{budget:,}',
        currency_name=currency_names.get(currency, 'دينار عراقي'),
        car_type=car_type_names.get(car_type, 'أي نوع'),
        condition=condition_names.get(condition, 'مستعمل'),
    )

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens': 2000,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content']

        content = content.strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1]
        if content.endswith('```'):
            content = content.rsplit('```', 1)[0]
        content = content.strip()

        cars = json.loads(content)
        return {'success': True, 'cars': cars}

    except requests.exceptions.Timeout:
        logger.warning('DeepSeek API timeout')
        return {'success': False, 'error': 'الخادم يستغرق وقتاً أطول من المعتاد. حاول مرة أخرى.'}
    except requests.exceptions.RequestException as e:
        logger.error(f'DeepSeek API error: {e}')
        return {'success': False, 'error': 'حدث خطأ في الاتصال. حاول مرة أخرى.'}
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f'DeepSeek parse error: {e}')
        return {'success': False, 'error': 'لم نتمكن من تحليل النتيجة. حاول مرة أخرى.'}
