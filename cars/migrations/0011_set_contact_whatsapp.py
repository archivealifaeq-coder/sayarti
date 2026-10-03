from django.db import migrations


def set_contact_whatsapp(apps, schema_editor):
    SiteSettings = apps.get_model('cars', 'SiteSettings')
    settings, _ = SiteSettings.objects.get_or_create(pk=1)
    settings.contact_whatsapp_url = 'https://wa.me/9647737591530'
    settings.save(update_fields=['contact_whatsapp_url'])


def unset_contact_whatsapp(apps, schema_editor):
    SiteSettings = apps.get_model('cars', 'SiteSettings')
    SiteSettings.objects.filter(pk=1, contact_whatsapp_url='https://wa.me/9647737591530').update(contact_whatsapp_url='')


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0010_sitesettings_contact_telegram_url_and_more'),
    ]

    operations = [
        migrations.RunPython(set_contact_whatsapp, unset_contact_whatsapp),
    ]
