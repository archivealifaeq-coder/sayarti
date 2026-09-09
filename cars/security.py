import os


class SecurityHeadersMiddleware:
    """إضافة headers دفاعية لا تعتمد عليها Django افتراضياً."""

    def __init__(self, get_response):
        self.get_response = get_response
        admin_url = os.getenv('ADMIN_URL', 'admin/').strip().strip('/')
        self.admin_prefix = f'/{admin_url}/' if admin_url else '/admin/'

    def __call__(self, request):
        response = self.get_response(request)

        response.setdefault('Permissions-Policy', ', '.join([
            'accelerometer=()',
            'camera=()',
            'geolocation=()',
            'gyroscope=()',
            'magnetometer=()',
            'microphone=()',
            'payment=()',
            'usb=()',
            'browsing-topics=()',
        ]))
        response.setdefault('X-Permitted-Cross-Domain-Policies', 'none')
        response.setdefault('X-Download-Options', 'noopen')
        response.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        response.setdefault('Content-Security-Policy', self._content_security_policy())

        if request.path.startswith(self.admin_prefix):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response

    def _content_security_policy(self):
        return '; '.join([
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://www.googletagmanager.com https://www.google-analytics.com https://pagead2.googlesyndication.com https://googleads.g.doubleclick.net",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com",
            "font-src 'self' https://fonts.gstatic.com data:",
            "img-src 'self' data: blob: https:",
            "connect-src 'self' https://www.google-analytics.com https://analytics.google.com https://pagead2.googlesyndication.com https://googleads.g.doubleclick.net",
            "frame-src 'self' https://googleads.g.doubleclick.net https://tpc.googlesyndication.com",
            "worker-src 'self' blob:",
            "manifest-src 'self'",
            'upgrade-insecure-requests',
        ])
