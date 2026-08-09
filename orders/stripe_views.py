"""
Stripe決済処理 — 銀行振込と併用可能な手数料あり決済オプション。

Stripe APIは完全無料（従量課金は決済手数料のみ）。
APIキーは https://dashboard.stripe.com/apikeys で取得。
"""
import stripe
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from .models import Order, OrderItem, Payment
from .tasks import send_order_confirmation_email


stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def create_stripe_checkout_session(request, order_pk):
    """
    Stripe Checkout Sessionを作成し、決済ページにリダイレクト。
    """
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        pk=order_pk, user=request.user,
        status=Order.Status.PENDING,
        payment_method=Order.PaymentMethod.STRIPE,
    )

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Stripeが設定されていません。')
        return redirect('orders:order_detail', order_pk=order.pk)

    line_items = []
    for item in order.items.all():
        line_items.append({
            'price_data': {
                'currency': 'jpy',
                'product_data': {
                    'name': item.product_name,
                },
                'unit_amount': item.product_price,
            },
            'quantity': item.quantity,
        })

    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            client_reference_id=str(order.pk),
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri(
                reverse('orders:stripe_success', kwargs={'order_pk': order.pk})
            ),
            cancel_url=request.build_absolute_uri(
                reverse('orders:order_detail', kwargs={'order_pk': order.pk})
            ),
            metadata={
                'order_pk': str(order.pk),
                'order_number': order.order_number,
            },
        )
        return redirect(checkout_session.url, code=303)
    except stripe.error.StripeError as e:
        messages.error(request, f'決済セッションの作成に失敗しました: {e}')
        return redirect('orders:order_detail', order_pk=order.pk)


@login_required
def stripe_success_view(request, order_pk):
    """
    Stripe決済成功後のリダイレクト先。
    Webhookの着信を待たずに楽観的にステータスを更新するが、
    最終的な確定はWebhookで行う。
    """
    order = get_object_or_404(
        Order, pk=order_pk, user=request.user
    )
    messages.success(
        request,
        '決済が完了しました。入金確認メールをお送りします。'
    )
    return redirect('orders:order_detail', order_pk=order.pk)


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Stripe Webhook — 決済完了イベントを処理。
    Webhookシークレットは環境変数 STRIPE_WEBHOOK_SECRET で設定。
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    if endpoint_secret:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            return HttpResponse(f'Webhook error: {e}', status=400)
    else:
        # 開発モード: シークレットなしでも処理
        import json
        event = json.loads(payload)

    # 決済完了イベントを処理
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        _process_stripe_payment(session)

    return HttpResponse('OK', status=200)


def _process_stripe_payment(session):
    """Stripe Checkout完了時の注文確定処理。"""
    order_pk = session.get('metadata', {}).get('order_pk')
    if not order_pk:
        return

    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_pk)
        except Order.DoesNotExist:
            return

        if order.status != Order.Status.PENDING:
            return  # 既に処理済み

        # 注文確定
        order.status = Order.Status.PAID
        order.paid_at = timezone.now()
        order.save(update_fields=['status', 'paid_at'])

        # ダウンロード解放
        OrderItem.objects.filter(order=order).update(is_downloadable=True)

        # 決済レコード更新
        Payment.objects.filter(order=order).update(
            status=Payment.Status.CONFIRMED,
            confirmed_at=timezone.now(),
            notes=f'Stripe決済ID: {session.get("id", "")}',
        )

        # メール送信
        send_order_confirmation_email.delay(order.pk)
