from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Avg
from django.http import HttpResponseBadRequest

from .models import Product, Category, Shop, Review, Favorite
from orders.models import Order, OrderItem


def home_view(request):
    """Top page — new arrivals, popular products, categories."""
    new_products = Product.objects.filter(
        is_public=True, is_in_stock=True
    ).select_related('creator', 'category').prefetch_related('images')[:12]

    popular_products = Product.objects.filter(
        is_public=True, is_in_stock=True
    ).annotate(
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-review_count')[:10]

    # Featured shops/creators with most products
    featured_shops = Shop.objects.filter(
        is_public=True
    ).annotate(
        product_count=Count('products')
    ).filter(
        product_count__gt=0
    ).order_by('-product_count')[:8]

    context = {
        'new_products': new_products,
        'popular_products': popular_products,
        'featured_shops': featured_shops,
    }
    return render(request, 'shop/home.html', context)


def product_list_view(request, category_slug=None):
    """Product listing with optional category filter."""
    products = Product.objects.filter(is_public=True, is_in_stock=True)

    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        products = products.filter(category=category)

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(name__icontains=q)

    # Sort
    sort = request.GET.get('sort', '-created_at')
    allowed_sorts = {
        '-created_at': '-created_at',
        'created_at': 'created_at',
        'price': 'price',
        '-price': '-price',
        'name': 'name',
    }
    sort_field = allowed_sorts.get(sort, '-created_at')
    products = products.order_by(sort_field)

    products = products.select_related(
        'creator', 'category'
    ).prefetch_related('images').annotate(
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__rating')
    )

    context = {
        'products': products,
        'category': category,
        'query': q,
        'current_sort': sort,
    }
    return render(request, 'shop/product_list.html', context)


def product_detail_view(request, pk):
    """Product detail page with images, reviews, and creator info."""
    product = get_object_or_404(
        Product.objects.select_related('creator__user', 'category', 'shop'),
        pk=pk, is_public=True
    )
    images = product.images.all()
    reviews = Review.objects.filter(
        product=product, is_public=True
    ).select_related('user')[:20]

    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    review_count = reviews.count()

    creator_products = Product.objects.filter(
        creator=product.creator, is_public=True
    ).exclude(pk=product.pk)[:4]

    # 購入済み（入金確認済み）かつ未レビューの注文 — レビュー投稿フォーム用
    purchasable_orders = []
    is_favorited = False
    if request.user.is_authenticated:
        purchased_items = OrderItem.objects.filter(
            order__user=request.user,
            order__status__in=[Order.Status.PAID, Order.Status.SHIPPED],
            product=product,
        ).select_related('order')
        reviewed_order_ids = Review.objects.filter(
            product=product, user=request.user
        ).values_list('order_id', flat=True)
        purchasable_orders = [
            item.order for item in purchased_items
            if item.order_id not in reviewed_order_ids
        ]
        is_favorited = Favorite.objects.filter(
            user=request.user, product=product
        ).exists()

    context = {
        'product': product,
        'images': images,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'creator_products': creator_products,
        'purchasable_orders': purchasable_orders,
        'is_favorited': is_favorited,
    }
    return render(request, 'shop/product_detail.html', context)


@login_required
def review_create_view(request, pk):
    """レビュー投稿 — 購入済み（入金確認済み）ユーザーのみ."""
    product = get_object_or_404(
        Product.objects.select_related('creator'), pk=pk, is_public=True
    )
    if request.method != 'POST':
        return redirect('shop:product_detail', pk=product.pk)

    rating = request.POST.get('rating')
    comment = request.POST.get('comment', '').strip()
    order_pk = request.POST.get('order_pk')

    try:
        rating = int(rating)
        if not 1 <= rating <= 5:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, '評価は1〜5の数字で指定してください。')
        return redirect('shop:product_detail', pk=product.pk)

    order = Order.objects.filter(
        pk=order_pk, user=request.user,
        status__in=[Order.Status.PAID, Order.Status.SHIPPED],
    ).first()
    if order is None:
        messages.error(request, 'この商品を購入済みの注文がありません。')
        return redirect('shop:product_detail', pk=product.pk)

    # 同一注文での二重投稿防止（unique_together: product, user, order）
    if Review.objects.filter(
        product=product, user=request.user, order=order
    ).exists():
        messages.info(request, 'この注文では既にレビューを投稿済みです。')
        return redirect('shop:product_detail', pk=product.pk)

    Review.objects.create(
        product=product, user=request.user, order=order,
        rating=rating, comment=comment,
    )
    messages.success(request, 'レビューを投稿しました。ありがとうございます！')
    return redirect('shop:product_detail', pk=product.pk)


@login_required
def favorite_toggle_view(request, pk):
    """お気に入り追加/解除トグル."""
    product = get_object_or_404(Product, pk=pk, is_public=True)
    if request.method != 'POST':
        return redirect('shop:product_detail', pk=product.pk)

    favorite, created = Favorite.objects.get_or_create(
        user=request.user, product=product
    )
    if created:
        messages.success(request, 'お気に入りに追加しました。')
    else:
        favorite.delete()
        messages.info(request, 'お気に入りを解除しました。')
    return redirect('shop:product_detail', pk=product.pk)


@login_required
def favorite_list_view(request):
    """お気に入り一覧."""
    favorites = Favorite.objects.filter(
        user=request.user
    ).select_related('product__creator', 'product__category').prefetch_related('product__images')
    products = [f.product for f in favorites]
    context = {'favorites': favorites, 'products': products}
    return render(request, 'shop/favorites.html', context)


def shop_page_view(request, slug):
    """Creator's shop page."""
    shop = get_object_or_404(
        Shop.objects.select_related('creator__user'),
        slug=slug, is_public=True
    )
    products = Product.objects.filter(
        shop=shop, is_public=True, is_in_stock=True
    ).select_related('category').prefetch_related('images')[:30]

    context = {
        'shop': shop,
        'products': products,
        'creator': shop.creator,
    }
    return render(request, 'shop/shop_page.html', context)
