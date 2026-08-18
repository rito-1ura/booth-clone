"""
booth/sitemaps.py — サイトマップ生成。
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from shop.models import Product, Category, Shop
from django.utils import timezone


class StaticSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return [
            'shop:home',
            'shop:product_list',
            'accounts:signup',
            'accounts:login',
            'support',
            'terms',
            'privacy',
            'legal',
            'contact',
            'guide',
            'faq',
        ]

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Product.objects.filter(is_public=True, is_in_stock=True).select_related('category', 'creator')

    def lastmod(self, obj):
        return obj.updated_at or obj.created_at


class CategorySitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Category.objects.filter(is_active=True)


class ShopSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        return Shop.objects.filter(is_public=True).select_related('creator')

    def lastmod(self, obj):
        return obj.updated_at or obj.created_at