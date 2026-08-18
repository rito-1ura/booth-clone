"""
Main URL configuration for booth project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap

from . import pages
from .sitemaps import StaticSitemap, ProductSitemap, CategorySitemap, ShopSitemap

sitemaps = {
    'static': StaticSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'shops': ShopSitemap,
}

from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('shop.urls')),
    path('orders/', include('orders.urls')),
    path('creators/', include('creators.urls')),
    path('api/', include('api.urls')),
    # サポート / 静的ページ
    path('support/', pages.support_view, name='support'),
    path('terms/', pages.terms_view, name='terms'),
    path('privacy/', pages.privacy_view, name='privacy'),
    path('legal/', pages.legal_view, name='legal'),
    path('contact/', pages.contact_view, name='contact'),
    path('guide/', pages.guide_view, name='guide'),
    path('faq/', pages.faq_view, name='faq'),
    # SEO
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)