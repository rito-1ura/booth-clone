from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


@shared_task
def send_order_confirmation_email(order_pk):
    """Send order confirmation email asynchronously."""
    from orders.models import Order
    try:
        order = Order.objects.get(pk=order_pk)
    except Order.DoesNotExist:
        return f'Order {order_pk} not found'

    subject = f'【Booth Clone】注文確認 — {order.order_number}'
    message = f"""
{order.user.display_name} 様

ご注文ありがとうございます。

注文番号: {order.order_number}
注文日時: {timezone.localtime(order.created_at).strftime('%Y/%m/%d %H:%M')}
合計金額: ¥{order.total_amount:,}
決済方法: {order.get_payment_method_display()}
ステータス: {order.get_status_display()}

【決済方法別のご案内】
"""
    if order.payment_method == 'bank_transfer':
        message += """
お振込先:
  ○○銀行 普通預金 1234567
  ブース クローン

※3営業日以内にご入金ください。
※入金確認後、ダウンロードリンクが有効になります。
"""
    elif order.payment_method == 'paypay':
        message += """
PayPay ID: @booth_clone
上記IDに送金をお願いします。
"""

    message += f"""
ご注文内容:
{chr(10).join(f' ・{item.product_name} × {item.quantity} = ¥{item.subtotal:,}' for item in order.items.all())}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Booth Clone
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email],
        fail_silently=False,
    )
    return f'Order confirmation sent for {order.order_number}'


@shared_task
def notify_payment_confirmed(order_pk):
    """Notify buyer that payment is confirmed and download is available."""
    from orders.models import Order
    try:
        order = Order.objects.get(pk=order_pk)
    except Order.DoesNotExist:
        return f'Order {order_pk} not found'

    subject = f'【Booth Clone】入金確認完了 — {order.order_number}'
    message = f"""
{order.user.display_name} 様

入金を確認しました。ダウンロードが可能になりました。

注文番号: {order.order_number}
入金確認日時: {timezone.localtime(order.paid_at).strftime('%Y/%m/%d %H:%M')}

以下のURLからダウンロードできます。
https://{settings.ALLOWED_HOSTS[0]}/orders/detail/{order.pk}/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Booth Clone
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email],
        fail_silently=False,
    )
    return f'Payment confirmed notification sent for {order.order_number}'


@shared_task
def notify_new_withdrawal(withdrawal_pk):
    """Notify admin about a new withdrawal request."""
    from orders.models import Withdrawal
    try:
        withdrawal = Withdrawal.objects.select_related('creator').get(pk=withdrawal_pk)
    except Withdrawal.DoesNotExist:
        return f'Withdrawal {withdrawal_pk} not found'

    subject = '【Booth Clone】新しい売上引き出し申請があります'
    message = f"""
新しい売上引き出し申請が届きました。

クリエイター: {withdrawal.creator.pen_name}
金額: ¥{withdrawal.amount:,}
申請日時: {timezone.localtime(withdrawal.created_at).strftime('%Y/%m/%d %H:%M')}

管理画面で確認・処理してください。
https://{settings.ALLOWED_HOSTS[0]}/admin/orders/withdrawal/
"""
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.DEFAULT_FROM_EMAIL],
        fail_silently=False,
    )
    return f'Withdrawal notification sent for #{withdrawal.pk}'
