from rest_framework import viewsets, permissions, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Avg, Q
from django_filters.rest_framework import DjangoFilterBackend

from accounts.models import User, Creator
from shop.models import Category, Shop, Product, Review
from orders.models import Cart, CartItem, Order, OrderItem

from .serializers import (
    UserSerializer, CreatorSerializer,
    CategorySerializer, ShopSerializer,
    ProductListSerializer, ProductDetailSerializer,
    ReviewSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer,
)


# ============================
# Accounts
# ============================
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own profile
        return User.objects.filter(pk=self.request.user.pk)


# ============================
# Shop / Categories
# ============================
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True).order_by('sort_order')
    serializer_class = CategorySerializer
    lookup_field = 'slug'


class ShopViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Shop.objects.filter(is_public=True).select_related('creator').order_by('-created_at')
    serializer_class = ShopSerializer
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'creator__pen_name']


# ============================
# Products
# ============================
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category__slug', 'product_type', 'creator']
    search_fields = ['name', 'description', 'tags__tag_name']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve' or self.action == 'create' or self.action == 'update':
            return ProductDetailSerializer
        return ProductListSerializer

    def get_queryset(self):
        qs = Product.objects.filter(is_public=True, is_in_stock=True)
        qs = qs.select_related('category', 'creator', 'shop')
        qs = qs.prefetch_related('images', 'tags')
        qs = qs.annotate(
            review_count=Count('reviews', filter=Q(reviews__is_public=True)),
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_public=True)),
        )
        return qs

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        product = self.get_object()
        reviews = Review.objects.filter(
            product=product, is_public=True
        ).select_related('user').order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def popular(self, request):
        products = self.get_queryset().annotate(
            order_count=Count('order_items'),
        ).filter(order_count__gt=0).order_by('-order_count')[:20]
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def new_arrivals(self, request):
        products = self.get_queryset().order_by('-created_at')[:12]
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)


# ============================
# Cart
# ============================
class CartViewSet(viewsets.GenericViewSet):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def list(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add(self, request):
        from shop.models import Product
        product_pk = request.data.get('product')
        quantity = int(request.data.get('quantity', 1))

        product = Product.objects.get(pk=product_pk, is_public=True, is_in_stock=True)
        cart, _ = Cart.objects.get_or_create(user=request.user)

        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product,
            defaults={'quantity': quantity}
        )
        if not created:
            item.quantity += quantity
            item.save()

        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def remove(self, request):
        item_pk = request.data.get('item')
        cart = Cart.objects.get(user=request.user)
        CartItem.objects.filter(pk=item_pk, cart=cart).delete()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        cart = Cart.objects.get(user=request.user)
        cart.items.all().delete()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)


# ============================
# Orders
# ============================
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items').order_by('-created_at')
