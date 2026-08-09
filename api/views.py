from rest_framework import viewsets, permissions, filters, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Avg, Q
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404

from accounts.models import User, Creator
from shop.models import Category, Shop, Product, Review, Favorite
from orders.models import Cart, CartItem, Order, OrderItem, Withdrawal

from .serializers import (
    UserSerializer, CreatorSerializer,
    CategorySerializer, ShopSerializer,
    ProductListSerializer, ProductDetailSerializer,
    ReviewSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer,
    FavoriteSerializer, WithdrawalSerializer,
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

    @action(detail=True, methods=['get', 'post'])
    def reviews(self, request, pk=None):
        product = self.get_object()
        if request.method == 'POST':
            # レビュー投稿（購入済みユーザーのみ）
            if not request.user.is_authenticated:
                return Response(
                    {'detail': '認証が必要です。'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            rating = request.data.get('rating')
            comment = request.data.get('comment', '').strip()
            order_pk = request.data.get('order_pk')
            try:
                rating = int(rating)
            except (TypeError, ValueError):
                return Response(
                    {'rating': '1〜5の整数で指定してください。'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not 1 <= rating <= 5:
                return Response(
                    {'rating': '1〜5の整数で指定してください。'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # 購入済み（paid）注文の検証
            order = Order.objects.filter(
                user=request.user,
                items__product=product,
                status=Order.Status.PAID,
            ).distinct().order_by('-created_at').first()
            if order is None:
                return Response(
                    {'detail': 'この商品を購入済みのユーザーのみレビューできます。'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if order_pk:
                order = Order.objects.filter(
                    pk=order_pk, user=request.user, status=Order.Status.PAID,
                ).first()
                if order is None or not order.items.filter(product=product).exists():
                    return Response(
                        {'detail': '無効な注文です。'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            # 同一注文での二重投稿防止
            if Review.objects.filter(product=product, user=request.user, order=order).exists():
                return Response(
                    {'detail': 'この注文でのレビューは投稿済みです。'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            review = Review.objects.create(
                product=product, user=request.user, order=order,
                rating=rating, comment=comment or '',
            )
            serializer = ReviewSerializer(review, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

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


# ============================
# Favorites
# ============================
class FavoriteViewSet(viewsets.GenericViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(
            user=self.request.user
        ).select_related('product').order_by('-created_at')

    def list(self, request):
        favorites = self.get_queryset()
        serializer = self.get_serializer(favorites, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add(self, request):
        product_pk = request.data.get('product')
        product = get_object_or_404(
            Product, pk=product_pk, is_public=True, is_in_stock=True,
        )
        favorite, created = Favorite.objects.get_or_create(
            user=request.user, product=product,
        )
        serializer = self.get_serializer(favorite, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def remove(self, request):
        product_pk = request.data.get('product')
        Favorite.objects.filter(
            user=request.user, product_id=product_pk,
        ).delete()
        return Response({'detail': 'お気に入りを解除しました。'})

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        product_pk = request.data.get('product')
        product = get_object_or_404(
            Product, pk=product_pk, is_public=True, is_in_stock=True,
        )
        favorite, created = Favorite.objects.get_or_create(
            user=request.user, product=product,
        )
        if not created:
            favorite.delete()
            return Response({'favorited': False})
        return Response({'favorited': True})


# ============================
# Withdrawals (クリエイター専用)
# ============================
class WithdrawalViewSet(viewsets.GenericViewSet):
    serializer_class = WithdrawalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        creator = getattr(self.request.user, 'creator', None)
        if creator is None:
            return Withdrawal.objects.none()
        return Withdrawal.objects.filter(creator=creator).order_by('-created_at')

    def list(self, request):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def create(self, request):
        creator = getattr(request.user, 'creator', None)
        if creator is None:
            return Response(
                {'detail': 'クリエイターのみ出金申請できます。'},
                status=status.HTTP_403_FORBIDDEN,
            )
        # 銀行口座登録チェック
        if not (creator.bank_name and creator.bank_account_number):
            return Response(
                {'detail': '銀行口座が未登録です。プロフィールから登録してください。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            amount = int(request.data.get('amount', 0))
        except (TypeError, ValueError):
            return Response(
                {'amount': '金額を整数で指定してください。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if amount < 1000:
            return Response(
                {'amount': '出金金額は1,000円以上です。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if amount > creator.balance_yen:
            return Response(
                {'amount': '出金可能残高を超えています。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 二重送信防止（行ロック）+ 残高減算
        from django.db import transaction
        with transaction.atomic():
            creator = Creator.objects.select_for_update().get(pk=creator.pk)
            if amount > creator.balance_yen:
                return Response(
                    {'amount': '出金可能残高を超えています。'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            creator.balance_yen -= amount
            creator.save()
            withdrawal = Withdrawal.objects.create(
                creator=creator,
                amount=amount,
                bank_info=(
                    f'{creator.bank_name} {creator.bank_branch or ""} '
                    f'{creator.get_bank_account_type_display()} '
                    f'{creator.bank_account_number}'
                ).strip(),
            )
        # 管理者通知
        try:
            from orders.tasks import notify_new_withdrawal
            notify_new_withdrawal.delay(withdrawal.pk)
        except Exception:
            pass  # Celery 未設定時は通知をスキップ
        serializer = self.get_serializer(withdrawal)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
