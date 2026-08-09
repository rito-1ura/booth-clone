from django.conf import settings
from shop.models import Category


def site_settings(request):
    """Global context for all templates."""
    return {
        'SITE_NAME': 'Booth Clone',
        'categories': Category.objects.filter(is_active=True).order_by('sort_order'),
        'cart_count': request.session.get('cart_count', 0),
    }
