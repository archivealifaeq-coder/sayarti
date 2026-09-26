import os

from django.conf import settings
from django.core.checks import Critical, Error, Warning, Tags, register


@register(Tags.security, deploy=True)
def production_configuration_check(app_configs, **kwargs):
    issues = []

    allowed_hosts = set(getattr(settings, 'ALLOWED_HOSTS', []))
    local_hosts = {'localhost', '127.0.0.1', '0.0.0.0'}
    public_hosts = {host for host in allowed_hosts if host not in local_hosts and not host.startswith('192.168.')}
    if not public_hosts:
        issues.append(Error(
            'ALLOWED_HOSTS does not contain a public production domain.',
            hint='Set ALLOWED_HOSTS=sayarti.org,www.sayarti.org or the real deployment domain.',
            id='cars.E001',
        ))

    if not os.getenv('DATABASE_URL'):
        issues.append(Critical(
            'DATABASE_URL is not configured; production would use SQLite.',
            hint='Provision PostgreSQL and set DATABASE_URL before production deployment.',
            id='cars.C001',
        ))

    admin_url = os.getenv('ADMIN_URL', 'admin/').strip().strip('/')
    if not admin_url or admin_url == 'admin':
        issues.append(Warning(
            'ADMIN_URL is using the default admin path.',
            hint='Set ADMIN_URL to a private non-default path, for example site-control-2026/.',
            id='cars.W001',
        ))

    if not os.getenv('CSRF_TRUSTED_ORIGINS'):
        issues.append(Warning(
            'CSRF_TRUSTED_ORIGINS is not set explicitly.',
            hint='Set CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com.',
            id='cars.W002',
        ))

    if not os.getenv('BACKUP_GITHUB_REPO') or not os.getenv('GITHUB_BACKUP_TOKEN'):
        issues.append(Error(
            'Remote backups are not configured.',
            hint='Set BACKUP_GITHUB_REPO and GITHUB_BACKUP_TOKEN, or document another tested backup target.',
            id='cars.E002',
        ))

    if os.getenv('BACKUP_GITHUB_REPO') and not os.getenv('BACKUP_ENCRYPTION_PASSPHRASE'):
        issues.append(Warning(
            'Backup encryption passphrase is not configured.',
            hint='Set BACKUP_ENCRYPTION_PASSPHRASE so uploaded backups are encrypted.',
            id='cars.W003',
        ))

    if os.getenv('USE_S3', 'False').lower() == 'true':
        required_s3 = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_STORAGE_BUCKET_NAME', 'AWS_S3_ENDPOINT_URL']
        missing = [key for key in required_s3 if not os.getenv(key)]
        if missing:
            issues.append(Error(
                'S3 media storage is enabled but incomplete.',
                hint='Missing: ' + ', '.join(missing),
                id='cars.E003',
            ))

    return issues
