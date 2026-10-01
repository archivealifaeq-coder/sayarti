from .models import AdBanner, SiteSettings


def site_settings(request):
    return {
        'site_settings': SiteSettings.load(),
        'ticker_banners': AdBanner.objects.filter(is_active=True, position='ticker').order_by('order', '-created_at'),
    }
