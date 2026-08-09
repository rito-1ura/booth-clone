"""
PayPal決済処理 — 銀行振込と併用可能な手数料あり決済オプション。

PayPal APIは完全無料（従量課金は決済手数料のみ）。
認証情報: https://developer.paypal.com/dashboard/applications
"""
import requests
from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from .models import Order, OrderItem, Payment
from .tasks import send_order_confirmation_email
from .services import finalize_auto_payment


PAYPAL_API_BASE = 'https://api-m.paypal.com'
PAYPAL_SANDBOX_BASE = 'https://api-m.sandbox.paypal.com'


def _paypal_base():
    if getattr(settings, 'PAYPAL_SANDBOX', False):
        return PAYPAL_SANDBOX_BASE
    return PAYPAL_API_BASE


def _get_access_token():
    """Get PayPal OAuth2 access token."""
    url = f'{_paypal_base()}/v1/oauth2/token'
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET)
    resp = requests.post(
        url, data={'grant_type': 'client_credentials'},
        auth=auth, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()['access_token']


@login_required
def create_paypal_payment(request, order_pk):
    """
    PayPal Orderを作成し、承認リンクへリダイレクト。
    """
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        pk=order_pk, user=request.user,
        status=Order.Status.PENDING,
        payment_method=Order.PaymentMethod.PAYPAL,
    )

    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
        messages.error(request, 'PayPalが設定されていません。')
        return redirect('orders:order_detail', order_pk=order.pk)

    try:
        token = _get_access_token()
        url = f'{_paypal_base()}/v2/checkout/orders'

        purchase_items = []
        for item in order.items.all():
            purchase_items.append({
                'name': item.product_name[:127],
                'quantity': str(item.quantity),
                'unit_amount': {
                    'currency_code': 'JPY',
                    'value': f'{item.product_price:.2f}',
                },
            })

        payload = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'reference_id': str(order.pk),
                'amount': {
                    'currency_code': 'JPY',
                    'value': f'{order.total_amount:.2f}',
                    'breakdown': {
                        'item_total': {
                            'currency_code': 'JPY',
                            'value': f'{order.total_amount:.2f}',
                        },
                    },
                },
                'items': purchase_items,
                'description': f'Booth Clone注文 {order.order_number}',
            }],
            'application_context': {
                'brand_name': 'Booth Clone',
                'user_action': 'PAY_NOW',
                'return_url': request.build_absolute_uri(
                    reverse('orders:paypal_capture', kwargs={'order_pk': order.pk})
                ),
                'cancel_url': request.build_absolute_uri(
                    reverse('orders:order_detail', kwargs={'order_pk': order.pk})
                ),
            },
        }

        resp = requests.post(
            url, json=payload,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        # PayPal Order IDを保存（キャプチャ時に照合）
        order.paypal_order_id = data['id']
        order.save(update_fields=['paypal_order_id'])

        # 承認リンクを探す
        for link in data.get('links', []):
            if link['rel'] == 'approve':
                return redirect(link['href'])

        messages.error(request, 'PayPal承認リンクが見つかりませんでした。')
    except requests.RequestException as e:
        messages.error(request, f'PayPal決済の作成に失敗しました: {e}')
    return redirect('orders:order_detail', order_pk=order.pk)


@login_required
def capture_paypal_payment(request, order_pk):
    """
    PayPal承認後のリターンURL。決済を確定する。
    """
    order = get_object_or_404(
        Order, pk=order_pk, user=request.user,
        payment_method=Order.PaymentMethod.PAYPAL,
    )

    paypal_order_id = request.GET.get('token') or order.paypal_order_id
    if not paypal_order_id:
        messages.error(request, 'PayPal注文IDが見つかりません。')
        return redirect('orders:order_detail', order_pk=order.pk)

    try:
        token = _get_access_token()
        url = f'{_paypal_base()}/v2/checkout/orders/{paypal_order_id}/capture'
        resp = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get('status') != 'COMPLETED':
            messages.error(request, 'PayPal決済が完了していません。')
            return redirect('orders:order_detail', order_pk=order.pk)

        capture = data.get('purchase_units', [{}])[0].get('payments', {}).get('captures', [{}])[0]
        capture_id = capture.get('id', '')

        # 注文確定（冪等: 二重captureでも売上は一度だけ加算）
        processed = finalize_auto_payment(order, f'PayPal決済ID: {capture_id}')
        if processed:
            messages.success(request, 'PayPal決済が完了しました。ダウンロードが可能になりました。')
        else:
            messages.success(request, 'この注文は既に処理済みです。')
    except requests.RequestException as e:
        messages.error(request, f'PayPal決済の確定に失敗しました: {e}')
    return redirect('orders:order_detail', order_pk=order.pk)
