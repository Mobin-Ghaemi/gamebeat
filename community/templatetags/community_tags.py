from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
import re

register = template.Library()


@register.filter
def hashtagify(text):
    escaped = escape(text)

    def replace(m):
        tag = m.group(1)
        url = reverse('community:hashtag_feed', args=[tag.lower()])
        return f'<a href="{url}" class="hashtag-link">#{tag}</a>'

    return mark_safe(re.sub(r'#([a-zA-Z؀-ۿ\w]{2,50})', replace, escaped))
