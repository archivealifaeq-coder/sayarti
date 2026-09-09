from django.db import models
from django.core.cache import cache
from django.core.validators import MinValueValidator, MaxValueValidator


class CarSpecification(models.Model):
    id = models.IntegerField(primary_key=True)
    brand_en = models.CharField(max_length=100)
    brand_ar = models.CharField(max_length=100)
    model_en = models.CharField(max_length=100)
    model_ar = models.CharField(max_length=100)

    brand_norm = models.CharField(max_length=100, blank=True, default='', db_index=True)
    model_norm = models.CharField(max_length=100, blank=True, default='', db_index=True)
    
    year = models.IntegerField(
        validators=[
            MinValueValidator(1900, message="السنة يجب أن تكون 1900 أو أكثر"),
            MaxValueValidator(2099, message="السنة يجب أن تكون 2099 أو أقل")
        ]
    )
    spec = models.CharField(max_length=100, blank=True, null=True)

    trim = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="الفئة (Trim)",
        help_text="مثال: GLX، EX، سمارت، فل كامل"
    )

    ENGINE_TYPE_CHOICES = [
        ('regular', 'عادي'),
        ('hybrid', 'هايبرد'),
        ('turbo', 'تيربو'),
        ('diesel', 'ديزل'),
        ('electric', 'كهربائي'),
    ]
    engine_type = models.CharField(
        max_length=20,
        choices=ENGINE_TYPE_CHOICES,
        default='regular',
        verbose_name="نوع المحرك"
    )

    SPEC_REGION_CHOICES = [
        ('gcc', 'خليجي'),
        ('american', 'أمريكي'),
        ('european', 'أوروبي'),
        ('japanese', 'ياباني'),
        ('chinese', 'صيني'),
        ('other', 'أخرى'),
    ]
    spec_region = models.CharField(
        max_length=20,
        choices=SPEC_REGION_CHOICES,
        default='gcc',
        verbose_name="مواصفات المنطقة"
    )

    engine = models.CharField(max_length=100)
    engine_norm = models.CharField(max_length=100, blank=True, default='')
    oil_visc = models.CharField(max_length=50)
    oil_visc_high_km = models.CharField(max_length=50, blank=True, null=True)
    fuel = models.CharField(max_length=50)
    
    octane = models.IntegerField(
        validators=[
            MinValueValidator(80, message="رقم الأوكتان يجب أن يكون 80 أو أكثر"),
            MaxValueValidator(120, message="رقم الأوكتان يجب أن يكون 120 أو أقل")
        ]
    )
    
    spark = models.CharField(max_length=100)

    tire_size = models.CharField(
        max_length=50,
        verbose_name="حجم الإطار",
        default="غير محدد",
        help_text="مثال: 215/60R16"
    )

    oil_capacity = models.CharField(max_length=50)
    recommendations = models.TextField(blank=True, null=True)
    oil_brands = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ماركات الزيت",
        help_text="مثال: Mobil 1, Castrol, Total"
    )

    battery = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="البطارية (الحجم/السعة)",
        help_text="مثال: 55D23L، 60Ah، 12V 70Ah"
    )

    transmission_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="نوع ناقل الحركة",
        help_text="مثال: أوتوماتيك 6 سرعات، CVT، Manual"
    )

    transmission_oil_spec = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="مواصفات زيت الناقل",
        help_text="مثال: ATF WS، ATF SP-III، Dexron VI"
    )

    transmission_oil_brands = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ماركات زيت الناقل",
        help_text="مثال: Toyota Genuine ATF, Idemitsu, AISIN"
    )

    class Meta:
        indexes = [
            models.Index(fields=['brand_ar']),
            models.Index(fields=['model_ar']),
            models.Index(fields=['year']),
            models.Index(fields=['engine_type']),
            models.Index(fields=['spec_region']),
        ]

    def __str__(self):
        return f"{self.brand_ar} - {self.model_ar} ({self.year})"


class Sponsor(models.Model):
    """شركة راعية (مثال: زيت الحسام) لديها أكواد خصم يولدها الموقع لزواره.

    كل شركة لها بادئة كود ونسبة خصم وصفحة تحقق خاصة لموظفها.
    """
    name = models.CharField(max_length=150, verbose_name="اسم الشركة")
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name="المعرّف (slug)",
        help_text="يُستخدم في رابط صفحة التحقق — مثال: hisam → sayarti.org/verify/hisam/"
    )
    code_prefix = models.CharField(
        max_length=20,
        verbose_name="بادئة الكود",
        help_text="بداية الكود المولّد — مثال: HISAM → كود مثل HISAM-4821"
    )
    discount = models.IntegerField(
        default=10,
        verbose_name="نسبة الخصم %",
        help_text="تُعرض للزائر عند توليد الكود وتظهر لموظف الشركة في الفحص"
    )
    website = models.URLField(
        blank=True,
        verbose_name="الموقع / صفحة الشركة",
        help_text="اختياري — يُعرض كرابط للزائر للمزيد حول الشركة"
    )
    password = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="كلمة مرور حساب الراعي",
        help_text="يستخدمها الراعي لتسجيل الدخول إلى «نافذة الخدمات» للتحقق من الأكواد — تُخزَّن مشفّرة"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="مفعل",
        help_text="✔️ نشطة والأكواد تُولَّد منها | ❌ متوقفة"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإضافة")

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "شركة راعية"
        verbose_name_plural = "الشركات الراعية"


class PromoCode(models.Model):
    STATUS_CHOICES = [
        ('active', 'ساري (غير مستخدم)'),
        ('used', 'مُستخدم'),
    ]

    code = models.CharField(
        max_length=40,
        unique=True,
        verbose_name="الكود",
        help_text="يُولَّد تلقائياً — مثال HISAM-4821"
    )
    sponsor = models.ForeignKey(
        Sponsor,
        on_delete=models.CASCADE,
        related_name='codes',
        verbose_name="الشركة المولّدة",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="الحالة",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ التوليد", db_index=True)
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الاستخدام", db_index=True)
    verified_by = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name="تم التحقق من قبل",
        help_text="اسم الشركة التي فحصت واستخدمت الكود"
    )

    def __str__(self):
        return self.code

    class Meta:
        ordering = ['-created_at']
        verbose_name = "كود خصم"
        verbose_name_plural = "أكواد الخصم"


class AdBanner(models.Model):
    POSITION_CHOICES = [
        ('ticker', '📢 شريط متحرك علوي (5%) - أعلى الصفحة'),
        ('slider', '🎠 سلايدر رئيسي (35%) - وسط الصفحة'),
    ]

    sponsor = models.ForeignKey(
        Sponsor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="الشركة الراعية",
        related_name='banners',
        help_text="اربط البنر بشركة راعية ليظهر فيها زر «احصل على خصم»"
    )

    title = models.CharField(max_length=200, verbose_name="العنوان")
    subtitle = models.CharField(max_length=200, blank=True, null=True, verbose_name="العنوان الفرعي")
    
    image = models.ImageField(
        upload_to='banners/',
        blank=True,
        null=True,
        verbose_name="صورة البنر (سطح المكتب)",
        help_text="📐 الأبعاد الموصى بها: 1920 × 820 بكسل (نسبة 21:9) — الصورة تُقص تلقائياً"
    )
    
    image_mobile = models.ImageField(
        upload_to='banners/mobile/',
        blank=True,
        null=True,
        verbose_name="صورة البنر للهواتف",
        help_text="📱 الأبعاد الموصى بها: 800 × 600 بكسل (نسبة 4:3)"
    )
    
    background_color = models.CharField(
        max_length=50,
        default="from-blue-700 via-indigo-700 to-purple-700",
        verbose_name="لون الخلفية",
        help_text="يستخدم هذا اللون إذا لم ترفع صورة"
    )
    text_color = models.CharField(
        max_length=20,
        default="text-white",
        verbose_name="لون النص",
        help_text="text-white أو text-black"
    )
    button_text = models.CharField(
        max_length=50,
        default="اعرف المزيد",
        verbose_name="نص الزر"
    )
    button_url = models.URLField(
        default="#",
        blank=True,
        verbose_name="رابط الزر",
        help_text="مثال: /offers/ أو https://example.com"
    )
    position = models.CharField(
        max_length=20,
        choices=POSITION_CHOICES,
        default='ticker',
        verbose_name="الموقع"
    )
    order = models.IntegerField(
        default=0,
        verbose_name="الترتيب",
        help_text="0 = يظهر أولاً"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="مفعل",
        help_text="✔️ ظاهر في الموقع | ❌ مخفي"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return f"{self.title} ({self.get_position_display()})"

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "بنر إعلاني"
        verbose_name_plural = "البنرات الإعلانية"


class FeatureCard(models.Model):
    title = models.CharField(max_length=100, verbose_name="العنوان")
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="الوصف"
    )
    icon = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="الأيقونة",
        help_text="إيموجي مثل 🚗 🔧 🧮 ⭐ — اتركه فارغاً إذا استخدمت صورة إعلان"
    )
    image = models.ImageField(
        upload_to='feature_ads/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="صورة إعلان",
        help_text="إن وُجدت تُعرض بدل الأيقونة — مثالي لإعلانات الرعاة"
    )
    link = models.URLField(
        blank=True,
        verbose_name="رابط البطاقة",
        help_text="عند تعبئته تصبح البطاقة قابلة للنقر (إعلان)"
    )
    sponsor = models.ForeignKey(
        Sponsor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="الشركة الراعية",
        related_name='feature_cards',
        help_text="اربط البطاقة بشركة راعية ليظهر فيها زر «احصل على خصم»"
    )
    order = models.IntegerField(
        default=0,
        verbose_name="الترتيب",
        help_text="0 = تظهر أولاً"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="مفعلة",
        help_text="✔️ ظاهرة في الموقع | ❌ مخفية"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = "بطاقة مميزات"
        verbose_name_plural = "بطاقات المميزات"


class MarketCarPrice(models.Model):
    ORIGIN_CHOICES = [
        ('all', 'عام'),
        ('japanese', 'ياباني'),
        ('korean', 'كوري'),
        ('chinese', 'صيني'),
        ('american', 'أمريكي'),
        ('german', 'ألماني'),
        ('european', 'أوروبي'),
        ('iranian', 'إيراني'),
    ]
    BODY_TYPE_CHOICES = [
        ('all', 'عام'),
        ('sedan', 'سيدان'),
        ('suv', 'SUV / عائلي'),
        ('pickup', 'بيكب'),
        ('hatchback', 'هاتشباك'),
        ('van', 'فان'),
        ('coupe', 'كوبيه'),
    ]
    CONDITION_CHOICES = [
        ('used', 'مستعمل'),
        ('new', 'جديد'),
    ]
    id1 = models.PositiveBigIntegerField(null=True, blank=True, unique=True, db_index=True, verbose_name='ID خارجي')
    name = models.CharField(max_length=180, verbose_name='اسم السيارة الكامل')
    brand = models.CharField(max_length=100, verbose_name='الماركة عربي')
    brand_en = models.CharField(max_length=100, blank=True, verbose_name='الماركة إنجليزي')
    model = models.CharField(max_length=100, verbose_name='الموديل عربي')
    model_en = models.CharField(max_length=100, blank=True, verbose_name='الموديل إنجليزي')
    brand_norm = models.CharField(max_length=100, blank=True, default='', db_index=True)
    model_norm = models.CharField(max_length=100, blank=True, default='', db_index=True)
    year = models.IntegerField(validators=[MinValueValidator(1990), MaxValueValidator(2099)], verbose_name='السنة')
    trim = models.CharField(max_length=80, blank=True, verbose_name='الفئة / الكلاس')
    origin = models.CharField(max_length=20, choices=ORIGIN_CHOICES, default='all', db_index=True, verbose_name='المنشأ')
    body_type = models.CharField(max_length=20, choices=BODY_TYPE_CHOICES, default='all', db_index=True, verbose_name='نوع الجسم')
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default='used', db_index=True, verbose_name='الحالة')
    price_iqd = models.PositiveBigIntegerField(db_index=True, verbose_name='السعر بالدينار')
    price_usd = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name='السعر بالدولار')
    engine = models.CharField(max_length=80, blank=True, verbose_name='المحرك')
    fuel_economy = models.CharField(max_length=50, blank=True, default='جيد', verbose_name='صرف الوقود')
    maintenance = models.CharField(max_length=50, blank=True, default='متوسطة', verbose_name='الصيانة')
    pros = models.CharField(max_length=240, blank=True, verbose_name='سبب الترشيح')
    source_name = models.CharField(max_length=120, blank=True, verbose_name='مصدر السعر')
    source_url = models.URLField(blank=True, verbose_name='رابط المصدر')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='مفعل')
    confidence = models.PositiveSmallIntegerField(default=80, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='درجة الثقة')
    updated_at = models.DateTimeField(auto_now=True, db_index=True, verbose_name='آخر تحديث')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')

    class Meta:
        ordering = ['-year', 'price_iqd', '-confidence', 'brand', 'model']
        indexes = [
            models.Index(fields=['condition', 'origin', 'body_type', 'price_iqd']),
            models.Index(fields=['condition', 'origin', 'body_type', 'price_usd']),
            models.Index(fields=['brand_norm', 'model_norm']),
        ]
        verbose_name = 'سعر سيارة في السوق'
        verbose_name_plural = 'أسعار السيارات في السوق'

    def save(self, *args, **kwargs):
        from .services.textnorm import fold_ar
        self.brand_norm = fold_ar(self.brand)
        self.model_norm = fold_ar(self.model)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.year})'

SITE_SETTINGS_CACHE_KEY = 'site_settings_obj'
SITE_SETTINGS_CACHE_TTL = 60


class SiteSettings(models.Model):
    """Global site settings - singleton row (ID=1)."""
    show_ads = models.BooleanField(
        default=False,
        verbose_name="تفعيل الإعلانات",
        help_text="شغّلها بعد قبول موقعك في Google AdSense"
    )
    adsense_client_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="معرف الناشر AdSense",
        help_text="مثال: ca-pub-1234567890123456"
    )
    ad_slot_results = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="رقم الوحدة: نتائج البحث",
        help_text="data-ad-slot من لوحة AdSense"
    )
    ad_slot_recommend_top = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="رقم الوحدة: أعلى صفحة التوصيات",
        help_text="data-ad-slot من لوحة AdSense"
    )
    ad_slot_recommend_bottom = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="رقم الوحدة: أسفل صفحة التوصيات",
        help_text="data-ad-slot من لوحة AdSense"
    )
    ads_txt = models.TextField(
        blank=True,
        verbose_name="محتوى ads.txt",
        help_text="يُعرض على /ads.txt — الصق السطر الذي يعطيك إياه AdSense مثال: google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0"
    )
    ga4_id = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="معرف تحليلات Google (GA4)",
        help_text="من analytics.google.com — مثال: G-ABC123XYZ — يسجّل زوار الموقع والصفحات والدول"
    )
    ga4_property_id = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="معرف الخاصية (Property ID)",
        help_text="من GA4 Admin → Property settings — مثال: 15522423744"
    )
    ga_service_account_json = models.TextField(
        blank=True,
        verbose_name="مفتاح الخدمة (Service Account JSON)",
        help_text="الصق محتوى ملف JSON لخدمة الحساب بعد تفعيل Analytics Data API — يسمح بعرض عدد الزوار في لوحة الإدارة"
    )
    groq_api_key = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="مفتاح Groq (حائط صد أخير)",
        help_text="من console.groq.com — يستخدم في شكد فلوسك فقط إذا فشل DeepSeek وGemini"
    )
    gemini_api_key = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="مفتاح Gemini (احتياطي)",
        help_text="من aistudio.google.com — احتياطي إذا تعطل DeepSeek"
    )
    deepseek_api_key = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="مفتاح DeepSeek API (الأساسي)",
        help_text="مفتاح API من platform.deepseek.com — المزود الأساسي لميزة شكد فلوسك"
    )
    exchange_rate_iqd_per_usd = models.PositiveIntegerField(
        default=1500,
        verbose_name="سعر صرف الدولار مقابل الدينار",
        help_text="سعر السوق الموازي: كم دينار عراقي لكل 1 دولار. يُستخدم لحساب السعر الناقص عند استيراد أسعار شكد فلوسك."
    )
    exchange_rate_source = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="مصدر سعر الصرف"
    )

    def __str__(self):
        return "إعدادات الموقع"

    class Meta:
        verbose_name = "إعدادات الموقع"
        verbose_name_plural = "إعدادات الموقع"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    @classmethod
    def load(cls):
        obj = cache.get(SITE_SETTINGS_CACHE_KEY)
        if obj is not None:
            return obj
        obj, _ = cls.objects.get_or_create(pk=1)
        cache.set(SITE_SETTINGS_CACHE_KEY, obj, SITE_SETTINGS_CACHE_TTL)
        return obj
