from rest_framework import serializers
from accounts.models import User, Creator
from shop.models import Category, Shop, Product, ProductImage, ProductTag, Review
from orders.models import Cart, CartItem, Order, OrderItem, Payment


# ============================
# Accounts
# ============================
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'display_name', 'avatar', 'is_creator', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class CreatorSerializer(serializers.ModelSerializer):
    pen_name = serializers.CharField(source='user.display_name', read_only=True)

    class Meta:
        model = Creator
        fields = [
            'id', 'pen_name', 'profile', 'header_image',
            'twitter_url', 'pixiv_url', 'website_url',
            'is_verified', 'total_sales',
        ]


# ============================
# Shop / Category
# ============================
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'sort_order']


class ShopSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.pen_name', read_only=True)

    class Meta:
        model = Shop
        fields = ['id', 'name', 'slug', 'description', 'theme_color', 'creator_name']


# ============================
# Products
# ============================
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_main', 'sort_order']


class ProductTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductTag
        fields = ['tag_name']


class ProductListSerializer(serializers.ModelSerializer):
    """Compact product representation for list endpoints."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    creator_name = serializers.CharField(source='creator.pen_name', read_only=True)
    main_image = serializers.SerializerMethodField()
    review_count = serializers.IntegerField(read_only=True, default=0)
    avg_rating = serializers.FloatField(read_only=True, default=None)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'price', 'product_type',
            'category_name', 'creator_name',
            'is_in_stock', 'is_public',
            'main_image', 'review_count', 'avg_rating',
            'published_at', 'created_at',
        ]

    def get_main_image(self, obj):
        main = obj.images.filter(is_main=True).first()
        if main and main.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(main.image.url)
            return main.image.url
        # Fallback to first image
        first = obj.images.first()
        if first and first.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(first.image.url)
            return first.image.url
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full product representation."""
    category = CategorySerializer(read_only=True)
    creator = CreatorSerializer(read_only=True)
    shop = ShopSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    tags = ProductTagSerializer(many=True, read_only=True)
    review_count = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'product_type',
            'stock_quantity', 'is_in_stock',
            'file_size_mb', 'download_limit', 'download_expiry_days',
            'category', 'creator', 'shop',
            'images', 'tags',
            'review_count', 'avg_rating',
            'is_public', 'published_at', 'created_at', 'updated_at',
        ]

    def get_review_count(self, obj):
        return obj.reviews.filter(is_public=True).count()

    def get_avg_rating(self, obj):
        from django.db.models import Avg
        return obj.reviews.filter(is_public=True).aggregate(
            avg=Avg('rating')
        )['avg']


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.display_name', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'rating', 'comment', 'user_name', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


# ============================
# Orders
# ============================
class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.IntegerField(source='product.price', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_name', 'product_price', 'quantity', 'subtotal']

    def get_subtotal(self, obj):
        return obj.subtotal()


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total']

    def get_total(self, obj):
        return sum(item.subtotal() for item in obj.items.all())


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_name', 'product_price', 'quantity', 'subtotal',
            'is_downloadable', 'download_count',
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(
        source='get_payment_method_display', read_only=True
    )

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'total_amount', 'status', 'status_display',
            'payment_method', 'payment_method_display',
            'items', 'created_at', 'paid_at',
        ]
        read_only_fields = ['id', 'order_number', 'created_at']
