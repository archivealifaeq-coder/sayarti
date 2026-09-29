"""Excel schemas and import/export operations for admin-managed data."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from cars.models import AdBanner, Dealer, PromoCode, Sponsor

from .admin_excel import bool_value, datetime_value, int_value, read_excel_rows, text_value


SPONSOR_HEADERS = ("name", "slug", "code_prefix", "discount", "website", "is_active")
PROMO_CODE_HEADERS = ("code", "sponsor_slug", "status", "created_at", "used_at", "verified_by")
DEALER_HEADERS = (
    "id", "dealer_type", "parts_region", "name", "governorate", "address", "phone",
    "whatsapp", "website", "brands", "description", "is_active", "is_featured", "order",
)
AD_BANNER_HEADERS = (
    "id", "sponsor_slug", "title", "subtitle", "position", "gateway_card_target",
    "target_dealer_id", "background_color", "text_color", "button_text", "button_url",
    "order", "is_active", "image_reference", "mobile_image_reference",
)


def _require(row, *headers):
    missing = [header for header in headers if not text_value(row, header)]
    if missing:
        raise ValidationError(f"الحقول المطلوبة فارغة: {', '.join(missing)}")


def _result():
    return {"created": 0, "updated": 0, "failed": 0, "errors": []}


def _record_error(result, row, exc):
    result["failed"] += 1
    if len(result["errors"]) < 15:
        messages = getattr(exc, "messages", None) or [str(exc)]
        result["errors"].append(f"الصف {row.get('__row_number__', '?')}: {' '.join(messages)}")


def sponsor_rows(queryset):
    return [
        {
            "name": item.name,
            "slug": item.slug,
            "code_prefix": item.code_prefix,
            "discount": item.discount,
            "website": item.website,
            "is_active": item.is_active,
        }
        for item in queryset.order_by("name")
    ]


@transaction.atomic
def import_sponsors(uploaded_file):
    result = _result()
    for row in read_excel_rows(uploaded_file, ("Sponsors", "الشركات الراعية")):
        try:
            _require(row, "name")
            name = text_value(row, "name")
            sponsor_slug = text_value(row, "slug") or slugify(name, allow_unicode=False)
            if not sponsor_slug:
                raise ValidationError("تعذر توليد slug؛ اكتبه صراحة في الملف.")
            prefix = text_value(row, "code_prefix") or sponsor_slug.upper()[:20]
            sponsor, created = Sponsor.objects.update_or_create(
                slug=sponsor_slug,
                defaults={
                    "name": name,
                    "code_prefix": prefix,
                    "discount": int_value(row, "discount", 10),
                    "website": text_value(row, "website"),
                    "is_active": bool_value(row, "is_active", True),
                },
            )
            sponsor.full_clean(exclude=("password",))
            sponsor.save()
            result["created" if created else "updated"] += 1
        except Exception as exc:
            _record_error(result, row, exc)
    return result


def promo_code_rows(queryset):
    return [
        {
            "code": item.code,
            "sponsor_slug": item.sponsor.slug,
            "status": item.status,
            "created_at": item.created_at,
            "used_at": item.used_at,
            "verified_by": item.verified_by,
        }
        for item in queryset.select_related("sponsor").order_by("-created_at")
    ]


@transaction.atomic
def import_promo_codes(uploaded_file):
    result = _result()
    valid_statuses = {key for key, _ in PromoCode.STATUS_CHOICES}
    for row in read_excel_rows(uploaded_file, ("PromoCodes", "أكواد الخصم")):
        try:
            _require(row, "code", "sponsor_slug")
            sponsor = Sponsor.objects.filter(slug=text_value(row, "sponsor_slug")).first()
            if not sponsor:
                raise ValidationError("sponsor_slug لا يطابق شركة راعية موجودة.")
            status = text_value(row, "status", "active") or "active"
            if status not in valid_statuses:
                raise ValidationError("status يجب أن تكون active أو used.")
            code, created = PromoCode.objects.update_or_create(
                code=text_value(row, "code").upper(),
                defaults={
                    "sponsor": sponsor,
                    "status": status,
                    "used_at": datetime_value(row, "used_at"),
                    "verified_by": text_value(row, "verified_by"),
                },
            )
            code.full_clean()
            code.save()
            result["created" if created else "updated"] += 1
        except Exception as exc:
            _record_error(result, row, exc)
    return result


def dealer_rows(queryset):
    return [
        {header: getattr(item, header) for header in DEALER_HEADERS}
        for item in queryset.order_by("dealer_type", "parts_region", "name")
    ]


@transaction.atomic
def import_dealers(uploaded_file):
    result = _result()
    dealer_types = {key for key, _ in Dealer.DEALER_TYPE_CHOICES}
    regions = {key for key, _ in Dealer.PARTS_REGION_CHOICES}
    for row in read_excel_rows(uploaded_file, ("Dealers", "الوكلاء")):
        try:
            _require(row, "name", "dealer_type")
            dealer_type = text_value(row, "dealer_type")
            region = text_value(row, "parts_region", "all") or "all"
            if dealer_type not in dealer_types or region not in regions:
                raise ValidationError("dealer_type أو parts_region غير صحيحة.")
            defaults = {
                "parts_region": region,
                "name": text_value(row, "name"),
                "governorate": text_value(row, "governorate"),
                "address": text_value(row, "address"),
                "phone": text_value(row, "phone"),
                "whatsapp": text_value(row, "whatsapp"),
                "website": text_value(row, "website"),
                "brands": text_value(row, "brands"),
                "description": text_value(row, "description"),
                "is_active": bool_value(row, "is_active", True),
                "is_featured": bool_value(row, "is_featured", False),
                "order": int_value(row, "order", 0),
            }
            object_id = int_value(row, "id", 0)
            if object_id:
                dealer, created = Dealer.objects.update_or_create(id=object_id, defaults={"dealer_type": dealer_type, **defaults})
            else:
                dealer, created = Dealer.objects.update_or_create(
                    dealer_type=dealer_type,
                    name=text_value(row, "name"),
                    governorate=text_value(row, "governorate"),
                    defaults=defaults,
                )
            dealer.full_clean()
            dealer.save()
            result["created" if created else "updated"] += 1
        except Exception as exc:
            _record_error(result, row, exc)
    return result


def banner_rows(queryset):
    rows = []
    for item in queryset.select_related("sponsor", "target_dealer").order_by("position", "order"):
        rows.append({
            "id": item.id,
            "sponsor_slug": item.sponsor.slug if item.sponsor_id else "",
            "title": item.title,
            "subtitle": item.subtitle or "",
            "position": item.position,
            "gateway_card_target": item.gateway_card_target,
            "target_dealer_id": item.target_dealer_id or "",
            "background_color": item.background_color,
            "text_color": item.text_color,
            "button_text": item.button_text,
            "button_url": item.button_url,
            "order": item.order,
            "is_active": item.is_active,
            "image_reference": item.image.name if item.image else "",
            "mobile_image_reference": item.image_mobile.name if item.image_mobile else "",
        })
    return rows


@transaction.atomic
def import_banners(uploaded_file):
    result = _result()
    valid_positions = {key for key, _ in AdBanner.POSITION_CHOICES}
    valid_targets = {key for key, _ in AdBanner.GATEWAY_CARD_TARGET_CHOICES}
    for row in read_excel_rows(uploaded_file, ("AdBanners", "البنرات")):
        try:
            _require(row, "title")
            position = text_value(row, "position", "ticker") or "ticker"
            target = text_value(row, "gateway_card_target")
            if position not in valid_positions or target not in valid_targets:
                raise ValidationError("position أو gateway_card_target غير صحيحة.")
            sponsor_slug = text_value(row, "sponsor_slug")
            sponsor = Sponsor.objects.filter(slug=sponsor_slug).first() if sponsor_slug else None
            if sponsor_slug and not sponsor:
                raise ValidationError("sponsor_slug لا يطابق شركة راعية موجودة.")
            target_dealer_id = int_value(row, "target_dealer_id", 0) or None
            if target_dealer_id and not Dealer.objects.filter(id=target_dealer_id).exists():
                raise ValidationError("target_dealer_id لا يطابق وكيلاً موجوداً.")
            defaults = {
                "sponsor": sponsor,
                "title": text_value(row, "title"),
                "subtitle": text_value(row, "subtitle") or None,
                "position": position,
                "gateway_card_target": target,
                "target_dealer_id": target_dealer_id,
                "background_color": text_value(row, "background_color", "from-blue-700 via-indigo-700 to-purple-700"),
                "text_color": text_value(row, "text_color", "text-white"),
                "button_text": text_value(row, "button_text", "اعرف المزيد"),
                "button_url": text_value(row, "button_url", "#"),
                "order": int_value(row, "order", 0),
                "is_active": bool_value(row, "is_active", True),
            }
            object_id = int_value(row, "id", 0)
            if object_id:
                banner, created = AdBanner.objects.update_or_create(id=object_id, defaults=defaults)
            else:
                banner, created = AdBanner.objects.update_or_create(
                    title=defaults["title"], position=position, defaults=defaults,
                )
            # Image references are deliberately report-only; binary files stay in protected media storage.
            banner.full_clean(exclude=("image", "image_mobile"))
            banner.save()
            result["created" if created else "updated"] += 1
        except Exception as exc:
            _record_error(result, row, exc)
    return result
