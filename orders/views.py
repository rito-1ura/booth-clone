import uuid
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.conf import settings
from shop.models import Product
from .models import Cart, CartItem, Order, OrderItem, Payment, DownloadLog
from .tasks import send_order_confirmation_email, notify_payment_confirmed
from .stripe_views import create_stripe_checkout_session, stripe_success_view, stripe_webhook_view
from .paypal_views import create_paypal_payment, capture_paypal_payment


def _get_cart(request):
    """Get or create the current user's cart."""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(
            user=None, session_key=session_key
        )
    return cart


def cart_add_view(request, product_pk):
    """Add a product to the cart."""
    product = get_object_or_404(Product, pk=product_pk, is_public=True, is_in_stock=True)
    cart = _get_cart(request)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    # Update cart count in session
    request.session['cart_count'] = cart.items.count()

    messages.success(request, f'{product.name} をカートに追加しました。')
    return redirect('orders:cart_detail')


def cart_detail_view(request):
    """Display cart contents."""
    cart = _get_cart(request)
    items = cart.items.select_related('product__creator').all()
    total = sum(item.subtotal() for item in items)
    context = {
        'cart': cart,
        'items': items,
        'total': total,
    }
    return render(request, 'orders/cart.html', context)


def cart_remove_view(request, item_pk):
    """Remove an item from cart."""
    cart = _get_cart(request)
    item = get_object_or_404(CartItem, pk=item_pk, cart=cart)
    item.delete()
    request.session['cart_count'] = cart.items.count()
    messages.success(request, '商品をカートから削除しました。')
    return redirect('orders:cart_detail')


@login_required
def checkout_view(request):
    """Checkout page — enter shipping info, select payment method."""
    cart = _get_cart(request)
    items = cart.items.select_related('product').all()

    if not items:
        messages.warning(request, 'カートが空です。')
        return redirect('shop:product_list')

    total = sum(item.subtotal() for item in items)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'bank_transfer')
        shipping_name = request.POST.get('shipping_name', '')
        shipping_zip = request.POST.get('shipping_zip', '')
        shipping_address = request.POST.get('shipping_address', '')
        shipping_phone = request.POST.get('shipping_phone', '')

        with transaction.atomic():
            # Generate order number
            today = timezone.now()
            date_str = today.strftime('%Y%m%d')
            order_count = Order.objects.filter(
                created_at__date=today.date()
            ).count() + 1
            order_number = f'BO-{date_str}-{order_count:03d}'

            # Create order
            order = Order.objects.create(
                order_number=order_number,
                user=request.user,
                total_amount=total,
                status=Order.Status.PENDING,
                payment_method=payment_method,
                shipping_name=shipping_name,
                shipping_zip=shipping_zip,
                shipping_address=shipping_address,
                shipping_phone=shipping_phone,
            )

            # Create order items and update stock
            for cart_item in items:
                product = cart_item.product
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    product_price=product.price,
                    quantity=cart_item.quantity,
                    subtotal=cart_item.subtotal(),
                )

                # Update stock for physical products
                if product.product_type == 'physical' and product.stock_quantity is not None:
                    product.stock_quantity -= cart_item.quantity
                    if product.stock_quantity <= 0:
                        product.is_in_stock = False
                    product.save(update_fields=['stock_quantity', 'is_in_stock'])

            # Create payment record
            Payment.objects.create(
                order=order,
                payment_method=payment_method,
                amount=total,
            )

            # Clear cart
            cart.items.all().delete()
            request.session['cart_count'] = 0

            # Send order confirmation via Celery
            send_order_confirmation_email.delay(order.pk)

        # Stripe/PayPal決済の場合は決済ページへリダイレクト
        if payment_method == Order.PaymentMethod.STRIPE:
            return redirect('orders:stripe_create_session', order_pk=order.pk)
        if payment_method == Order.PaymentMethod.PAYPAL:
            return redirect('orders:paypal_create', order_pk=order.pk)

        return redirect('orders:order_complete', order_pk=order.pk)

    context = {
        'items': items,
        'total': total,
        'stripe_enabled': bool(settings.STRIPE_SECRET_KEY),
        'paypal_enabled': bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET),
    }
    return render(request, 'orders/checkout.html', context)


@login_required
def order_complete_view(request, order_pk):
    """Order completion page."""
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        pk=order_pk, user=request.user
    )
    return render(request, 'orders/order_complete.html', {'order': order})


@login_required
def order_history_view(request):
    """Order history for the current user."""
    orders = Order.objects.filter(user=request.user).prefetch_related('items')
    return render(request, 'orders/order_history.html', {'orders': orders})


@login_required
def order_detail_view(request, order_pk):
    """Single order detail with download links."""
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product', 'payment'),
        pk=order_pk, user=request.user
    )
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
def download_view(request, item_pk):
    """Download a digital product file."""
    item = get_object_or_404(
        OrderItem.objects.select_related('order', 'product'),
        pk=item_pk, order__user=request.user
    )

    # Validation
    if not item.is_downloadable:
        messages.error(request, '入金確認後にダウンロードが可能になります。')
        return redirect('orders:order_detail', order_pk=item.order.pk)

    if item.download_count >= item.product.download_limit:
        messages.error(request, 'ダウンロード回数の上限に達しました。')
        return redirect('orders:order_detail', order_pk=item.order.pk)

    # Check expiry
    if item.product.download_expiry_days:
        expiry_date = item.order.paid_at + timedelta(
            days=item.product.download_expiry_days
        )
        if timezone.now() > expiry_date:
            messages.error(request, 'ダウンロード有効期限が切れています。')
            return redirect('orders:order_detail', order_pk=item.order.pk)

    file_path = item.product.file_path
    if not file_path:
        messages.error(request, 'ファイルが見つかりません。')
        return redirect('orders:order_detail', order_pk=item.order.pk)

    # Log download
    DownloadLog.objects.create(
        order_item=item,
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )

    # Update download count
    item.download_count += 1
    item.last_downloaded_at = timezone.now()
    item.save(update_fields=['download_count', 'last_downloaded_at'])

    # Serve the file — S3互換ストレージ対応
    from django.core.files.storage import default_storage

    file_path_full = str(settings.MEDIA_ROOT / str(file_path))
    try:
        if settings.USE_S3:
            # S3: 署名付きURLを返してリダイレクト（AWS_QUERYSTRING_AUTH=True時）
            response = redirect(default_storage.url(file_path))
        else:
            with open(file_path_full, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="{item.product_name}"'
        return response
    except FileNotFoundError:
        raise Http404('ファイルが見つかりませんでした。')
