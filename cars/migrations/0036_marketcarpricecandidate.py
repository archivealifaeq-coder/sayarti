from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0035_delete_ai_budget_market_prices'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketCarPriceCandidate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id1', models.PositiveBigIntegerField(blank=True, db_index=True, null=True, verbose_name='ID خارجي')),
                ('raw_title', models.CharField(blank=True, max_length=240, verbose_name='عنوان الإعلان الأصلي')),
                ('name', models.CharField(max_length=180, verbose_name='اسم السيارة الكامل')),
                ('brand', models.CharField(max_length=100, verbose_name='الماركة عربي')),
                ('brand_en', models.CharField(blank=True, max_length=100, verbose_name='الماركة إنجليزي')),
                ('model', models.CharField(max_length=100, verbose_name='الموديل عربي')),
                ('model_en', models.CharField(blank=True, max_length=100, verbose_name='الموديل إنجليزي')),
                ('year', models.IntegerField(validators=[MinValueValidator(1990), MaxValueValidator(2099)], verbose_name='السنة')),
                ('origin', models.CharField(choices=[('all', 'عام'), ('japanese', 'ياباني'), ('korean', 'كوري'), ('chinese', 'صيني'), ('american', 'أمريكي'), ('german', 'ألماني'), ('european', 'أوروبي'), ('iranian', 'إيراني')], db_index=True, default='all', max_length=20, verbose_name='المنشأ')),
                ('body_type', models.CharField(choices=[('all', 'عام'), ('sedan', 'سيدان'), ('suv', 'SUV / عائلي'), ('pickup', 'بيكب'), ('hatchback', 'هاتشباك'), ('van', 'فان'), ('coupe', 'كوبيه')], db_index=True, default='all', max_length=20, verbose_name='نوع الجسم')),
                ('condition', models.CharField(choices=[('used', 'مستعمل'), ('new', 'جديد')], db_index=True, default='used', max_length=10, verbose_name='الحالة')),
                ('price_iqd', models.PositiveBigIntegerField(db_index=True, verbose_name='السعر بالدينار')),
                ('price_usd', models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name='السعر بالدولار')),
                ('source_name', models.CharField(blank=True, max_length=120, verbose_name='مصدر السعر')),
                ('source_url', models.URLField(blank=True, db_index=True, verbose_name='رابط المصدر')),
                ('confidence', models.PositiveSmallIntegerField(default=60, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='درجة الثقة')),
                ('status', models.CharField(choices=[('pending', 'بانتظار المراجعة'), ('approved', 'معتمد'), ('rejected', 'مرفوض')], db_index=True, default='pending', max_length=12, verbose_name='الحالة')),
                ('notes', models.CharField(blank=True, max_length=240, verbose_name='ملاحظات المراجعة')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='آخر تحديث')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')),
            ],
            options={
                'verbose_name': 'سعر مقترح من الإنترنت',
                'verbose_name_plural': 'أسعار مقترحة من الإنترنت',
                'ordering': ['status', '-updated_at', '-year', 'price_iqd'],
            },
        ),
        migrations.AddIndex(
            model_name='marketcarpricecandidate',
            index=models.Index(fields=['status', 'condition', 'origin', 'body_type'], name='cars_market_status_04ff5e_idx'),
        ),
        migrations.AddIndex(
            model_name='marketcarpricecandidate',
            index=models.Index(fields=['brand', 'model', 'year'], name='cars_market_brand_7e0869_idx'),
        ),
    ]
