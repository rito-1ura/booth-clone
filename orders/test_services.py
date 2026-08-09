"""
orders/services.py — 売上確定・手数料計算のテスト。

実テストで発見されたバグの回帰テスト:
自動決済（PayPal/Stripe）でクリエイター残高・手数料が未処理だった問題。
"""
from django.test import TestCase
from django.utils import timezone

from accounts.models import User, Creator
from shop.models import Category, Shop, Product
from orders.models import Order, OrderItem, Payment
from orders.services import calculate_fee, finalize_auto_payment


def _make_order(payment_method, amount=3000):
    user = User.objects.create_user(
        email='svc-buyer@example.com', username='svcbuyer',
        display_name='購入者', password='p1234'
    )
    creator_user = User.objects.create_user(
        email='svc-creator@example.com', username='svccreator',
        display_name='出品者', password='p1234'
    )
    creator = Creator.objects.create(user=creator_user, pen_name='工房')
    shop = Shop.objects.create(creator=creator, name='店', slug='svc-mise')
    cat = Category.objects.create(name='カテゴリ', slug='svc-cat')
    product = Product.objects.create(
        creator=creator, shop=shop, category=cat,
        name='商品', description='説明', price=amount,
        is_public=True, is_in_stock=True,
    )
    order = Order.objects.create(
        user=user, order_number=f'SVC-{payment_method}', total_amount=amount,
        payment_method=payment_method, status=Order.Status.PENDING,
    )
    OrderItem.objects.create(
        order=order, product=product, product_name=product.name,
        product_price=amount, quantity=1, subtotal=amount,
    )
    Payment.objects.create(order=order, amount=amount, payment_method=payment_method)
    return order, creator


class CalculateFeeTests(TestCase):
    def test_paypal_fee_3_4_percent_plus_40(self):
        # 3000円 → 3000*0.034=102 → +40 = 142
        self.assertEqual(calculate_fee(3000, Order.PaymentMethod.PAYPAL), 142)

    def test_stripe_fee_3_6_percent_plus_40(self):
        # 3000円 → 3000*0.036=108 → +40 = 148
        self.assertEqual(calculate_fee(3000, Order.PaymentMethod.STRIPE), 148)

    def test_bank_transfer_no_fee(self):
        self.assertEqual(calculate_fee(3000, Order.PaymentMethod.BANK_TRANSFER), 0)


class FinalizeAutoPaymentTests(TestCase):
    def test_paypal_finalize_adds_balance_and_fee(self):
        order, creator = _make_order(Order.PaymentMethod.PAYPAL)
        result = finalize_auto_payment(order, 'PayPal決済ID: CAP-001')

        self.assertTrue(result)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(order.fee_amount, 142)  # 3000 - 142 = 2858
        creator.refresh_from_db()
        self.assertEqual(creator.balance_yen, 2858)
        item = order.items.first()
        self.assertTrue(item.is_downloadable)
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, Payment.Status.CONFIRMED)
        self.assertIn('CAP-001', payment.notes)

    def test_stripe_finalize_adds_balance_and_fee(self):
        order, creator = _make_order(Order.PaymentMethod.STRIPE)
        result = finalize_auto_payment(order, 'Stripe決済ID: cs_123')

        self.assertTrue(result)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.fee_amount, 148)  # 3000 - 148 = 2852
        creator.refresh_from_db()
        self.assertEqual(creator.balance_yen, 2852)

    def test_idempotent_no_double_credit(self):
        order, creator = _make_order(Order.PaymentMethod.PAYPAL)
        finalize_auto_payment(order, 'PayPal決済ID: CAP-001')
        creator.refresh_from_db()
        self.assertEqual(creator.balance_yen, 2858)

        # 二重capture（リダイレクト再訪問など）でも加算されない
        result = finalize_auto_payment(order, 'PayPal決済ID: CAP-001')
        self.assertFalse(result)
        creator.refresh_from_db()
        self.assertEqual(creator.balance_yen, 2858)
        order.refresh_from_db()
        self.assertEqual(order.fee_amount, 142)

    def test_explicit_fee_override(self):
        order, creator = _make_order(Order.PaymentMethod.PAYPAL)
        finalize_auto_payment(order, 'PayPal決済ID: CAP-001', fee=0)
        order.refresh_from_db()
        self.assertEqual(order.fee_amount, 0)
        creator.refresh_from_db()
        self.assertEqual(creator.balance_yen, 3000)
