"""
orders/services.py — 決済確定の共通ロジック。

自動決済（Stripe/PayPal）と手動入金確認で、売上・手数料を一貫して処理する。
- calculate_fee(): 決済手数料の計算（Stripe 3.6% + ¥40 / PayPal 3.4% + ¥40）
- finalize_auto_payment(): 自動決済の注文確定（冪等）
"""
from django.db import transaction
from django.utils import timezone

from .models import Order, OrderItem, Payment
from .tasks import send_order_confirmation_email


def calculate_fee(amount, payment_method):
    """決済手数料（円）。Stripe: 3.6% + ¥40 / PayPal: 3.4% + ¥40。それ以外は0。"""
    if payment_method == Order.PaymentMethod.STRIPE:
        return max(0, round(amount * 0.036) + 40)
    if payment_method == Order.PaymentMethod.PAYPAL:
        return max(0, round(amount * 0.034) + 40)
    return 0


def finalize_auto_payment(order, payment_reference, fee=None):
    """
    自動決済（Stripe/PayPal）の注文確定。

    - 冪等: 既に PAID の注文には何もせず False を返す（二重加算防止）
    - 注文を PAID + paid_at に更新し、手数料（fee_amount）を記録
    - 注文商品のダウンロードを解放
    - Payment レコードを CONFIRMED に更新（決済IDを notes に記録）
    - 売上（合計 - 手数料）をクリエイター残高へ加算
    - 購入者に確認メールを送信

    戻り値: 処理を実行したら True、既に処理済みなら False。
    """
    if fee is None:
        fee = calculate_fee(order.total_amount, order.payment_method)

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == Order.Status.PAID:
            return False

        order.status = Order.Status.PAID
        order.paid_at = timezone.now()
        order.fee_amount = fee
        order.save(update_fields=['status', 'paid_at', 'fee_amount'])

        OrderItem.objects.filter(order=order).update(is_downloadable=True)

        Payment.objects.filter(order=order).update(
            status=Payment.Status.CONFIRMED,
            confirmed_at=timezone.now(),
            notes=payment_reference,
        )

        # 売上 = 合計 - 手数料 を出品者残高へ加算
        first_item = order.items.select_related('product__creator').first()
        if first_item is not None:
            creator = first_item.product.creator
            creator.balance_yen += order.total_amount - fee
            creator.save(update_fields=['balance_yen'])

    send_order_confirmation_email.delay(order.pk)
    return True
