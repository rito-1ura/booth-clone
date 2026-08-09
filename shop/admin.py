from django.contrib import admin
from .models import Category, Shop, Product, ProductImage, ProductTag, Review, Favorite


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'creator', 'is_public')
    list_filter = ('is_public',)
    search_fields = ('name', 'creator__pen_name')
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
    fields = ('image', 'is_main', 'sort_order')


class ProductTagInline(admin.TabularInline):
    model = ProductTag
    extra = 2


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'price', 'creator', 'category',
        'product_type', 'is_public', 'is_in_stock'
    )
    list_filter = ('product_type', 'is_public', 'is_in_stock', 'category')
    search_fields = ('name', 'creator__pen_name')
    list_select_related = ('creator', 'category')
    inlines = [ProductImageInline, ProductTagInline]
    fieldsets = (
        (None, {
            'fields': (
                'creator', 'shop', 'category', 'name', 'description', 'price'
            )
        }),
        ('在庫・種別', {
            'fields': (
                'product_type', 'stock_quantity', 'is_in_stock'
            )
        }),
        ('デジタル商品', {
            'fields': (
                'file_path', 'file_size_mb', 'download_limit',
                'download_expiry_days'
            )
        }),
        ('公開設定', {
            'fields': ('is_public', 'published_at')
        }),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'is_public', 'created_at')
    list_filter = ('rating', 'is_public')
    search_fields = ('product__name', 'user__email', 'comment')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    search_fields = ('user__email', 'product__name')
    list_filter = ('created_at',)
