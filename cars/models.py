from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class CarSpecification(models.Model):
    id = models.IntegerField(primary_key=True)
    brand_en = models.CharField(max_length=100)
    brand_ar = models.CharField(max_length=100)
    model_en = models.CharField(max_length=100)
    model_ar = models.CharField(max_length=100)
    
    year = models.IntegerField(
        validators=[
            MinValueValidator(1900, message="السنة يجب أن تكون 1900 أو أكثر"),
            MaxValueValidator(2099, message="السنة يجب أن تكون 2099 أو أقل")
        ]
    )
    spec = models.CharField(max_length=100, blank=True, null=True)

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


class AdBanner(models.Model):
    POSITION_CHOICES = [
        ('ticker', '📢 شريط متحرك علوي (5%) - أعلى الصفحة'),
        ('slider', '🎠 سلايدر رئيسي (35%) - وسط الصفحة'),
    ]

    title = models.CharField(max_length=200, verbose_name="العنوان")
    subtitle = models.CharField(max_length=200, blank=True, null=True, verbose_name="العنوان الفرعي")
    
    image = models.ImageField(
        upload_to='banners/',
        blank=True,
        null=True,
        verbose_name="صورة البنر (سطح المكتب)",
        help_text="📐 الأبعاد الموصى بها: 1400 × 500 بكسل (نسبة 2.8:1)"
    )
    
    # ✅ حقل جديد للهواتف
    image_mobile = models.ImageField(
        upload_to='banners/mobile/',
        blank=True,
        null=True,
        verbose_name="صورة البنر للهواتف",
        help_text="📱 الأبعاد الموصى بها: 800 × 800 بكسل (نسبة 1:1)"
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

class SiteSettings(models.Model):
    """إعدادات عامة للموقع - سجل واحد فقط (ID=1)"""
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

    def __str__(self):
        return "إعدادات الموقع"

    class Meta:
        verbose_name = "إعدادات الموقع"
        verbose_name_plural = "إعدادات الموقع"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
