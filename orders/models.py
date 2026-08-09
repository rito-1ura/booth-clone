import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import User, Creator
from shop.models import Product


class Cart(models.Model):
    """Shopping cart (one per user or session)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='carts',
        null=True, blank=True
    )
    session_key = models.CharField(
        max_length=40, null=True, blank=True, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('cart')
        verbose_name_plural = _('carts')

    def __str__(self):
        owner = self.user.email if self.user else self.session_key
        return f'Cart ({owner})'


class CartItem(models.Model):
    """Item in a shopping cart."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='cart_items'
    )
    quantity = models.IntegerField(_('quantity'), default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('cart item')
        verbose_name_plural = _('cart items')
        unique_together = ('cart', 'product')

    def subtotal(self):
        return self.product.price * self.quantity


class Order(models.Model):
    """Purchase order."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('入金待ち')
        PAID = 'paid', _('入金確認済')
        SHIPPED = 'shipped', _('発送済')
        COMPLETED = 'completed', _('完了')
        CANCELLED = 'cancelled', _('キャンセル')

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'bank_transfer', _('銀行振込')
        CONVENIENCE = 'convenience', _('コンビニ支払い')
        PAYPAY = 'paypay', _('PayPay送金')
        STRIPE = 'stripe', _('クレジットカード (Stripe)')
        PAYPAL = 'paypal', _('PayPal')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        _('order number'), max_length=20, unique=True
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='orders'
    )
    total_amount = models.IntegerField(_('total amount'))
    fee_amount = models.IntegerField(_('fee'), default=0)
    shipping_amount = models.IntegerField(_('shipping'), default=0)
    status = models.CharField(
        _('status'), max_length=20,
        choices=Status.choices, default=Status.PENDING
    )
    payment_method = models.CharField(
        _('payment method'), max_length=20,
        choices=PaymentMethod.choices
    )
    # PayPal決済時のPayPal側Order ID（承認→キャプチャ照合用）
    paypal_order_id = models.CharField(
        _('paypal order id'), max_length=64, blank=True, default=''
    )

    # Shipping info (for physical goods)
    shipping_name = models.CharField(
        _('shipping name'), max_length=100, blank=True, default=''
    )
    shipping_zip = models.CharField(
        _('zip code'), max_length=8, blank=True, default=''
    )
    shipping_address = models.CharField(
        _('address'), max_length=255, blank=True, default=''
    )
    shipping_phone = models.CharField(
        _('phone'), max_length=15, blank=True, default=''
    )

    # Timestamps
    paid_at = models.DateTimeField(_('paid at'), null=True, blank=True)
    shipped_at = models.DateTimeField(_('shipped at'), null=True, blank=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('order')
        verbose_name_plural = _('orders')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', '-created_at']),
        ]

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    """Line item within an order (snapshot of product at purchase time)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='order_items'
    )
    product_name = models.CharField(_('product name'), max_length=200)
    product_price = models.IntegerField(_('price at order'))
    quantity = models.IntegerField(_('quantity'), default=1)
    subtotal = models.IntegerField(_('subtotal'))

    # Download management
    is_downloadable = models.BooleanField(_('downloadable'), default=False)
    download_count = models.IntegerField(_('download count'), default=0)
    last_downloaded_at = models.DateTimeField(
        _('last downloaded'), null=True, blank=True
    )

    class Meta:
        verbose_name = _('order item')
        verbose_name_plural = _('order items')

    def __str__(self):
        return f'{self.product_name} x{self.quantity}'


class Payment(models.Model):
    """Payment record (manual confirmation tracking)."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('入金待ち')
        CONFIRMED = 'confirmed', _('入金確認済')
        CANCELLED = 'cancelled', _('キャンセル')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name='payment'
    )
    payment_method = models.CharField(
        _('payment method'), max_length=20,
        choices=Order.PaymentMethod.choices
    )
    amount = models.IntegerField(_('amount'))
    status = models.CharField(
        _('status'), max_length=20,
        choices=Status.choices, default=Status.PENDING
    )
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confirmed_payments'
    )
    confirmed_at = models.DateTimeField(_('confirmed at'), null=True, blank=True)
    notes = models.TextField(_('notes'), blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')

    def __str__(self):
        return f'Payment for {self.order.order_number}'


class DownloadLog(models.Model):
    """Download history for digital products."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name='download_logs'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='download_logs'
    )
    ip_address = models.GenericIPAddressField(_('IP address'))
    user_agent = models.CharField(
        _('user agent'), max_length=500, blank=True, default=''
    )
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('download log')
        verbose_name_plural = _('download logs')

    def __str__(self):
        return f'{self.order_item} downloaded at {self.downloaded_at}'


class Withdrawal(models.Model):
    """Creator withdrawal request."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('申請中')
        PROCESSING = 'processing', _('処理中')
        COMPLETED = 'completed', _('完了')
        REJECTED = 'rejected', _('却下')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        Creator, on_delete=models.CASCADE, related_name='withdrawals'
    )
    amount = models.IntegerField(_('amount'))
    status = models.CharField(
        _('status'), max_length=20,
        choices=Status.choices, default=Status.PENDING
    )
    bank_info = models.TextField(
        _('bank info'),
        help_text=_('申請時点の振込先情報スナップショット')
    )
    processed_at = models.DateTimeField(
        _('processed at'), null=True, blank=True
    )
    notes = models.TextField(_('notes'), blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('withdrawal')
        verbose_name_plural = _('withdrawals')

    def __str__(self):
        return f'Withdrawal #{self.id} — ¥{self.amount} ({self.status})'
