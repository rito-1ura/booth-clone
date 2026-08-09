import uuid
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from accounts.models import Creator


class Category(models.Model):
    """Product categories with hierarchical structure."""
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name=_('parent category')
    )
    name = models.CharField(_('name'), max_length=50)
    slug = models.SlugField(_('slug'), max_length=50, unique=True)
    sort_order = models.IntegerField(_('sort order'), default=0)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['sort_order']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Shop(models.Model):
    """Creator's shop page."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField(
        Creator, on_delete=models.CASCADE, related_name='shop'
    )
    slug = models.SlugField(_('slug'), max_length=50, unique=True)
    name = models.CharField(_('shop name'), max_length=100)
    description = models.TextField(_('description'), blank=True, default='')
    theme_color = models.CharField(_('theme color'), max_length=7, default='#3B82F6')
    is_public = models.BooleanField(_('public'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('shop')
        verbose_name_plural = _('shops')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.creator.pen_name, allow_unicode=True)
            self.slug = base[:50]
        super().save(*args, **kwargs)


class Product(models.Model):
    """Product listing."""

    class ProductType(models.TextChoices):
        DIGITAL = 'digital', _('デジタル')
        PHYSICAL = 'physical', _('物理')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        Creator, on_delete=models.CASCADE, related_name='products'
    )
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='products'
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products'
    )
    name = models.CharField(_('name'), max_length=200)
    description = models.TextField(_('description'))
    price = models.IntegerField(_('price (yen)'), help_text=_('税込価格（円）'))
    product_type = models.CharField(
        _('product type'), max_length=20,
        choices=ProductType.choices, default=ProductType.DIGITAL
    )
    stock_quantity = models.IntegerField(
        _('stock quantity'), null=True, blank=True,
        help_text=_('NULL = 在庫無制限')
    )
    is_in_stock = models.BooleanField(_('in stock'), default=True)

    # Digital product fields
    file_path = models.FileField(
        _('file'), upload_to='products/files/', blank=True, null=True
    )
    file_size_mb = models.DecimalField(
        _('file size (MB)'), max_digits=8, decimal_places=2,
        blank=True, null=True
    )
    download_limit = models.IntegerField(_('download limit'), default=3)
    download_expiry_days = models.IntegerField(
        _('download expiry (days)'), default=30
    )

    # Publishing
    is_public = models.BooleanField(_('public'), default=False)
    published_at = models.DateTimeField(_('published at'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('product')
        verbose_name_plural = _('products')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['creator', 'is_public', 'published_at']),
            models.Index(fields=['category', 'is_public', '-created_at']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    """Product gallery images."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(_('image'), upload_to='products/')
    is_main = models.BooleanField(_('main image'), default=False)
    sort_order = models.IntegerField(_('sort order'), default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('product image')
        verbose_name_plural = _('product images')
        ordering = ['sort_order']


class ProductTag(models.Model):
    """Product tags (many-to-many via intermediate table)."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='tags'
    )
    tag_name = models.CharField(_('tag'), max_length=30, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('product tag')
        verbose_name_plural = _('product tags')
        unique_together = ('product', 'tag_name')

    def __str__(self):
        return self.tag_name


class Favorite(models.Model):
    """お気に入り（ブックマーク）— ユーザーごとの商品保存."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='favorites'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='favorited_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('favorite')
        verbose_name_plural = _('favorites')
        unique_together = ('user', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.display_name} ♥ {self.product.name}'


class Review(models.Model):
    """Product review by verified purchasers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='reviews'
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='reviews'
    )
    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='reviews'
    )
    rating = models.IntegerField(_('rating'), choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(_('comment'), blank=True, default='')
    is_public = models.BooleanField(_('public'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('review')
        verbose_name_plural = _('reviews')
        unique_together = ('product', 'user', 'order')
        indexes = [
            models.Index(fields=['product', 'is_public']),
        ]

    def __str__(self):
        return f'{self.product.name} - ★{self.rating} by {self.user.display_name}'
