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
    engine_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="كود المحرك",
        help_text="مثال: 2ZR-FE، G4NA، M274"
    )
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
    
    tire_size = models.CharField(
        max_length=50,
        verbose_name="حجم الإطار",
        default="غير محدد",
        help_text="مثال: 215/60R16"
    )
    spark = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="شمعات الاحتراق",
        help_text="مثال: NGK Iridium"
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
        ('gateway_grid', '💎 إعلان بين بطاقات الرئيسية'),
        ('gateway_card', '🏷️ رعاية صغيرة داخل بطاقات الرئيسية'),
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


class Dealer(models.Model):
    DEALER_TYPE_CHOICES = [
        ('oil', 'وكلاء الزيوت'),
        ('parts', 'وكلاء قطع الغيار'),
    ]
    PARTS_REGION_CHOICES = [
        ('all', 'عام'),
        ('japanese', 'ياباني'),
        ('chinese', 'صيني'),
        ('iranian', 'إيراني'),
        ('american', 'أمريكي'),
        ('german', 'ألماني'),
    ]

    dealer_type = models.CharField(max_length=12, choices=DEALER_TYPE_CHOICES, db_index=True, verbose_name='نوع الوكيل')
    parts_region = models.CharField(max_length=20, choices=PARTS_REGION_CHOICES, default='all', db_index=True, verbose_name='تصنيف قطع الغيار')
    name = models.CharField(max_length=160, verbose_name='اسم الوكيل')
    governorate = models.CharField(max_length=80, blank=True, verbose_name='المحافظة')
    address = models.CharField(max_length=220, blank=True, verbose_name='العنوان')
    phone = models.CharField(max_length=40, blank=True, verbose_name='رقم الهاتف')
    whatsapp = models.CharField(max_length=40, blank=True, verbose_name='رقم واتساب')
    website = models.URLField(blank=True, verbose_name='رابط الموقع / الصفحة')
    brands = models.CharField(max_length=220, blank=True, verbose_name='الماركات / الاختصاص')
    description = models.TextField(blank=True, verbose_name='تفاصيل الوكيل')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='ظاهر في الموقع')
    is_featured = models.BooleanField(default=False, db_index=True, verbose_name='وكيل مميز')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        ordering = ['dealer_type', 'parts_region', '-is_featured', 'order', 'name']
        indexes = [models.Index(fields=['dealer_type', 'parts_region', 'is_active'])]
        verbose_name = 'وكيل زيوت أو قطع غيار'
        verbose_name_plural = 'وكلاء الزيوت وقطع الغيار'

    def __str__(self):
        return self.name


class AppInstallMetric(models.Model):
    EVENT_CHOICES = [
        ('prompt_click', 'ضغط زر التثبيت'),
        ('installed', 'تثبيت فعلي'),
    ]
    event = models.CharField(max_length=20, choices=EVENT_CHOICES, unique=True, verbose_name='نوع الحدث')
    count = models.PositiveBigIntegerField(default=0, verbose_name='العدد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        ordering = ['event']
        verbose_name = 'عداد تثبيت التطبيق'
        verbose_name_plural = 'عدادات تثبيت التطبيق'

    def __str__(self):
        return self.get_event_display()


class DealerClickMetric(models.Model):
    ACTION_CHOICES = [
        ('phone', 'اتصال'),
        ('whatsapp', 'واتساب'),
        ('website', 'الموقع'),
    ]
    dealer = models.ForeignKey(Dealer, on_delete=models.CASCADE, related_name='click_metrics', verbose_name='الوكيل')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='نوع النقرة')
    count = models.PositiveBigIntegerField(default=0, verbose_name='العدد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        unique_together = [('dealer', 'action')]
        ordering = ['dealer__name', 'action']
        verbose_name = 'عداد تواصل وكيل'
        verbose_name_plural = 'عدادات تواصل الوكلاء'

    def __str__(self):
        return f'{self.dealer} - {self.get_action_display()}'

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
    show_dealers_card = models.BooleanField(
        default=False,
        verbose_name="إظهار بطاقة وكلاء الزيوت وقطع الغيار",
        help_text="فعّلها لإظهار بطاقة الوكلاء في واجهة الموقع، وألغها لإخفائها."
    )
    show_maintenance_card = models.BooleanField(
        default=False,
        verbose_name="إظهار بطاقة الصيانة والأعطال",
        help_text="فعّلها لإظهار بطاقة الصيانة والأعطال في واجهة الموقع، وألغها لإخفائها أثناء تجهيز البيانات."
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
        help_text="من console.groq.com — يستخدم في ميزات البحث الذكي فقط"
    )
    gemini_api_key = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="مفتاح Gemini (احتياطي)",
        help_text="من aistudio.google.com — يستخدم في ميزات البحث الذكي فقط"
    )
    deepseek_api_key = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="مفتاح DeepSeek API (الأساسي)",
        help_text="مفتاح API من platform.deepseek.com — يستخدم في ميزات البحث الذكي فقط"
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


class MaintenanceSeverity(models.TextChoices):
    LOW = 'low', 'منخفض'
    MEDIUM = 'medium', 'متوسط'
    HIGH = 'high', 'عالي'
    CRITICAL = 'critical', 'حرج'


class DrivingSafety(models.TextChoices):
    DRIVE_CAREFULLY = 'drive_carefully', 'يمكن القيادة بحذر'
    CHECK_SOON = 'check_soon', 'افحص قريباً'
    STOP_NOW = 'stop_now', 'أوقف السيارة'
    TOW_REQUIRED = 'tow_required', 'يفضل سطحة'


class OBDCode(models.Model):
    SYSTEM_CHOICES = [
        ('engine', 'المحرك'),
        ('transmission', 'ناقل الحركة'),
        ('emissions', 'الانبعاثات'),
        ('electrical', 'الكهرباء'),
        ('fuel', 'الوقود'),
        ('cooling', 'التبريد'),
        ('other', 'أخرى'),
    ]

    code = models.CharField(max_length=10, unique=True, db_index=True, verbose_name='كود العطل')
    title = models.CharField(max_length=180, verbose_name='العنوان')
    slug = models.SlugField(max_length=220, unique=True, verbose_name='رابط SEO')
    system = models.CharField(max_length=30, choices=SYSTEM_CHOICES, default='engine', verbose_name='النظام')
    severity = models.CharField(max_length=20, choices=MaintenanceSeverity.choices, default=MaintenanceSeverity.MEDIUM, verbose_name='درجة الخطورة')
    safety_status = models.CharField(max_length=30, choices=DrivingSafety.choices, default=DrivingSafety.CHECK_SOON, verbose_name='مؤشر الأمان')
    plain_explanation = models.TextField(verbose_name='شرح مبسط')
    local_explanation = models.TextField(blank=True, verbose_name='شرح باللهجة المحلية')
    common_causes = models.TextField(blank=True, verbose_name='الأسباب الشائعة')
    local_causes = models.TextField(blank=True, verbose_name='أسباب شائعة محلياً')
    symptoms = models.TextField(blank=True, verbose_name='الأعراض المتوقعة')
    self_check_steps = models.TextField(blank=True, verbose_name='خطوات فحص ذاتي')
    mechanic_advice = models.TextField(blank=True, verbose_name='نصيحة مراجعة المختص')
    dont_do = models.TextField(blank=True, verbose_name='أشياء لا تفعلها')
    estimated_cost_note = models.TextField(blank=True, verbose_name='ملاحظة التكلفة')
    seo_title = models.CharField(max_length=220, blank=True, verbose_name='عنوان SEO')
    seo_description = models.CharField(max_length=320, blank=True, verbose_name='وصف SEO')
    is_active = models.BooleanField(default=True, verbose_name='ظاهر في الموقع')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'كود عطل OBD'
        verbose_name_plural = 'أكواد الأعطال OBD'
        indexes = [models.Index(fields=['code']), models.Index(fields=['slug']), models.Index(fields=['system'])]

    def save(self, *args, **kwargs):
        self.code = (self.code or '').upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code} - {self.title}'


class CarSymptom(models.Model):
    CATEGORY_CHOICES = [
        ('engine', 'المحرك'),
        ('cooling', 'التبريد'),
        ('fuel', 'الوقود'),
        ('electrical', 'الكهرباء'),
        ('transmission', 'ناقل الحركة'),
        ('suspension', 'التعليق'),
        ('brakes', 'الفرامل'),
        ('tires', 'الإطارات'),
        ('other', 'أخرى'),
    ]

    name = models.CharField(max_length=160, unique=True, verbose_name='اسم العرض')
    slug = models.SlugField(max_length=200, unique=True, verbose_name='رابط SEO')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='engine', verbose_name='التصنيف')
    description = models.TextField(verbose_name='وصف العرض')
    severity = models.CharField(max_length=20, choices=MaintenanceSeverity.choices, default=MaintenanceSeverity.MEDIUM, verbose_name='درجة الخطورة')
    safety_status = models.CharField(max_length=30, choices=DrivingSafety.choices, default=DrivingSafety.CHECK_SOON, verbose_name='مؤشر الأمان')
    driver_questions = models.TextField(blank=True, verbose_name='أسئلة للسائق')
    self_check_steps = models.TextField(blank=True, verbose_name='خطوات فحص ذاتي')
    urgent_warning = models.TextField(blank=True, verbose_name='تحذير عاجل')
    seo_title = models.CharField(max_length=220, blank=True, verbose_name='عنوان SEO')
    seo_description = models.CharField(max_length=320, blank=True, verbose_name='وصف SEO')
    is_active = models.BooleanField(default=True, verbose_name='ظاهر في الموقع')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'عرض عطل'
        verbose_name_plural = 'أعراض الأعطال'
        indexes = [models.Index(fields=['slug']), models.Index(fields=['category'])]

    def __str__(self):
        return self.name


class SymptomCause(models.Model):
    LIKELIHOOD_CHOICES = [
        ('high', 'عالية'),
        ('medium', 'متوسطة'),
        ('low', 'منخفضة'),
    ]

    symptom = models.ForeignKey(CarSymptom, related_name='causes', on_delete=models.CASCADE, verbose_name='العرض')
    title = models.CharField(max_length=180, verbose_name='السبب المحتمل')
    description = models.TextField(blank=True, verbose_name='شرح السبب')
    priority = models.PositiveSmallIntegerField(default=1, verbose_name='الترتيب')
    likelihood = models.CharField(max_length=20, choices=LIKELIHOOD_CHOICES, default='medium', verbose_name='الاحتمالية')
    check_method = models.TextField(blank=True, verbose_name='طريقة الفحص')
    solution_hint = models.TextField(blank=True, verbose_name='إشارة للحل')
    related_obd_codes = models.CharField(max_length=120, blank=True, verbose_name='أكواد مرتبطة')
    is_active = models.BooleanField(default=True, verbose_name='ظاهر')

    class Meta:
        ordering = ['symptom', 'priority', 'id']
        verbose_name = 'سبب عرض'
        verbose_name_plural = 'أسباب الأعراض'

    def __str__(self):
        return f'{self.symptom}: {self.title}'


class MaintenanceTask(models.Model):
    CATEGORY_CHOICES = [
        ('oil', 'زيوت'),
        ('filters', 'فلاتر'),
        ('spark', 'شمعات القدح'),
        ('cooling', 'تبريد'),
        ('transmission', 'ناقل الحركة'),
        ('brakes', 'فرامل'),
        ('electrical', 'كهرباء'),
        ('tires', 'إطارات'),
        ('inspection', 'فحص عام'),
    ]
    APPLIES_CHOICES = [
        ('all', 'الكل'),
        ('gasoline', 'بنزين بدون تيربو'),
        ('gasoline_turbo', 'بنزين تيربو'),
        ('hybrid', 'هايبرد'),
        ('diesel', 'ديزل'),
        ('electric', 'كهربائي'),
    ]
    TRANSMISSION_CHOICES = [
        ('all', 'الكل'),
        ('automatic', 'أوتوماتيك'),
        ('cvt', 'CVT'),
        ('ecvt', 'e-CVT'),
        ('dct', 'DCT'),
        ('amt', 'AMT'),
        ('manual', 'عادي'),
    ]

    name = models.CharField(max_length=180, verbose_name='اسم المهمة')
    brand_ar = models.CharField(max_length=100, blank=True, verbose_name='الشركة بالعربي')
    brand_en = models.CharField(max_length=100, blank=True, verbose_name='الشركة بالإنكليزي')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='inspection', verbose_name='التصنيف')
    interval_km = models.PositiveIntegerField(default=10000, verbose_name='كل كم كيلومتر')
    interval_months = models.PositiveSmallIntegerField(default=12, verbose_name='كل كم شهر')
    severe_interval_km = models.PositiveIntegerField(default=5000, verbose_name='كل كم في الظروف الشاقة')
    severe_interval_months = models.PositiveSmallIntegerField(default=6, verbose_name='كل كم شهر في الظروف الشاقة')
    start_km = models.PositiveIntegerField(default=0, verbose_name='تبدأ من ممشى')
    importance = models.CharField(max_length=20, choices=MaintenanceSeverity.choices, default=MaintenanceSeverity.MEDIUM, verbose_name='الأهمية')
    description = models.TextField(blank=True, verbose_name='شرح المهمة')
    manufacturer_note = models.TextField(blank=True, verbose_name='توصية الشركة الأم')
    iraq_note = models.TextField(blank=True, verbose_name='ملاحظة للظروف العراقية')
    applies_to_engine_type = models.CharField(max_length=20, choices=APPLIES_CHOICES, default='all', verbose_name='نوع المحرك')
    applies_to_transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES, default='all', verbose_name='نوع ناقل الحركة')
    is_active = models.BooleanField(default=True, verbose_name='ظاهر في الموقع')

    class Meta:
        ordering = ['brand_ar', 'brand_en', 'start_km', 'severe_interval_km', 'name']
        verbose_name = 'مهمة صيانة'
        verbose_name_plural = 'مهام الصيانة'
        indexes = [
            models.Index(fields=['brand_ar']),
            models.Index(fields=['brand_en']),
            models.Index(fields=['category']),
            models.Index(fields=['start_km']),
            models.Index(fields=['severe_interval_km']),
        ]

    def __str__(self):
        return self.name
