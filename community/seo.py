import json
from urllib.parse import urljoin

from django.conf import settings
from django.templatetags.static import static
from django.utils.html import strip_tags


DEFAULT_DESCRIPTION = (
    'GameBeat کامیونیتی فارسی گیمرها برای پیدا کردن هم‌تیمی، دنبال کردن بازی‌ها، '
    'ثبت هایلایت، ریویو و ارتباط با گیمرهای دیگر است.'
)
DEFAULT_ROBOTS = 'index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1'


def _prune_schema(value):
    if isinstance(value, dict):
        cleaned = {key: _prune_schema(val) for key, val in value.items()}
        return {
            key: val for key, val in cleaned.items()
            if val not in (None, '', [], {})
        }
    if isinstance(value, list):
        cleaned = [_prune_schema(item) for item in value]
        return [item for item in cleaned if item not in (None, '', [], {})]
    return value


def normalize_text(value, limit=160):
    text = ' '.join(strip_tags(value or '').split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + '…'


def get_site_url(request=None):
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site_url:
        return site_url
    if request is None:
        return 'http://localhost:8000'
    return request.build_absolute_uri('/').rstrip('/')


def absolute_url(request, path_or_url=''):
    if not path_or_url:
        return get_site_url(request)
    if str(path_or_url).startswith(('http://', 'https://')):
        return path_or_url
    return urljoin(get_site_url(request) + '/', str(path_or_url).lstrip('/'))


def static_absolute(request, path):
    return absolute_url(request, static(path))


def make_breadcrumb_schema(items):
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {
                '@type': 'ListItem',
                'position': index + 1,
                'name': item['name'],
                'item': item['url'],
            }
            for index, item in enumerate(items)
        ],
    }


def make_organization_schema(request):
    site_url = get_site_url(request)
    return {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': 'GameBeat',
        'url': site_url,
        'logo': static_absolute(request, 'images/gamebeat-logo-wide.svg'),
        'sameAs': [],
    }


def make_website_schema(request):
    site_url = get_site_url(request)
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': 'GameBeat',
        'url': site_url,
        'inLanguage': 'fa',
        'potentialAction': {
            '@type': 'SearchAction',
            'target': absolute_url(request, '/search/global/?q={search_term_string}'),
            'query-input': 'required name=search_term_string',
        },
    }


def build_seo(
    request,
    *,
    title,
    description='',
    canonical=None,
    image=None,
    robots=DEFAULT_ROBOTS,
    schema=None,
    og_type='website',
):
    canonical_url = canonical or request.build_absolute_uri(request.path)
    image_url = absolute_url(request, image) if image else static_absolute(request, 'images/gamebeat-logo-wide.svg')
    data = {
        'title': title,
        'description': normalize_text(description or DEFAULT_DESCRIPTION, 170),
        'canonical': canonical_url,
        'robots': robots,
        'image': image_url,
        'og_type': og_type,
        'site_name': 'GameBeat',
        'schema_json': '',
    }
    if schema:
        schema_payload = _prune_schema(schema if isinstance(schema, list) else [schema])
        data['schema_json'] = json.dumps(schema_payload, ensure_ascii=False)
    return data
