"""
Stripe / PayPal 決済のモックテスト — APIキーなしで実行可能。

- Stripe: stripe.checkout.Session.create をモック
- PayPal: orders.paypal_views.requests.post をモック
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

import requests

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from accounts.models import Creator
from shop.models import Category, Shop, Product
from .models import Order, OrderItem, Payment

User = get_user_model()


def make_payment_order(user, creator, **kwargs):
    """注文と決済レコードを作成する共通ヘルパー。"""
    order = Order.objects.create(
        user=user,
        order_number=kwargs.pop('order_number', 'PAY-TEST-001'),
        total_amount=2000,
        payment_method=kwargs.pop('payment_method', 'stripe'),
        **kwargs,
    )
    Payment.objects.create(
        order=order,
        payment_method=order.payment_method,
        amount=order.total_amount,
    )
    return order


class PaymentSetupMixin:
    def setUp(self):
        self.user = User.objects.create_user(
            email='pay@example.com', username='payuser',
            display_name='決済ユーザー', password='p1234'
        )
        self.creator_user = User.objects.create_user(
            email='paycreator@example.com', username='paycreator',
            display_name='出品者', password='p1234'
        )
        self.creator = Creator.objects.create(
            user=self.creator_user, pen_name='決済工房'
        )
        self.shop = Shop.objects.create(
            creator=self.creator, name='決済店', slug='pay-mise'
        )
        self.cat = Category.objects.create(name='素材', slug='pay-sozai')
        self.product = Product.objects.create(
            creator=self.creator, shop=self.shop, category=self.cat,
            name='決済テスト素材', description='desc', price=2000,
            is_public=True, is_in_stock=True,
        )


# =============================================
# Stripe テスト
# =============================================
@override_settings(STRIPE_SECRET_KEY='sk_test_dummy', STRIPE_WEBHOOK_SECRET='')
class StripeTest(PaymentSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.order = make_payment_order(
            self.user, self.creator, payment_method='stripe'
        )
        OrderItem.objects.create(
            order=self.order, product=self.product,
            product_name='決済テスト素材', product_price=2000,
            quantity=1, subtotal=2000,
        )

    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_redirects(self, mock_create):
        """Session.create成功時、Stripeの決済URLへ303リダイレクト。"""
        mock_create.return_value = SimpleNamespace(
            url='https://checkout.stripe.com/pay/cs_test_abc'
        )
        self.client.force_login(self.user)
        url = reverse('orders:stripe_create_session', kwargs={'order_pk': self.order.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://checkout.stripe.com/pay/cs_test_abc')

        # 正しい引数で呼ばれたか検証
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['mode'], 'payment')
        self.assertEqual(kwargs['customer_email'], 'pay@example.com')
        self.assertEqual(kwargs['client_reference_id'], str(self.order.pk))
        self.assertEqual(kwargs['line_items'][0]['price_data']['unit_amount'], 2000)
        self.assertEqual(kwargs['metadata']['order_number'], 'PAY-TEST-001')

    @override_settings(STRIPE_SECRET_KEY='')
    def test_create_checkout_session_without_key(self):
        """キー未設定時はエラーメッセージ付きで注文詳細へ。"""
        self.client.force_login(self.user)
        url = reverse('orders:stripe_create_session', kwargs={'order_pk': self.order.pk})
        response = self.client.get(url)
        self.assertRedirects(
            response,
            reverse('orders:order_detail', kwargs={'order_pk': self.order.pk})
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_webhook_completes_order(self):
        """checkout.session.completed Webhookで注文が確定する。"""
        payload = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_webhook',
                    'metadata': {'order_pk': str(self.order.pk)},
                }
            }
        }
        response = self.client.post(
            reverse('orders:stripe_webhook'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertIsNotNone(self.order.paid_at)

        # ダウンロード解放
        item = self.order.items.first()
        self.assertTrue(item.is_downloadable)

        # 決済レコード更新
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, Payment.Status.CONFIRMED)
        self.assertIn('cs_test_webhook', payment.notes)

    def test_webhook_ignores_non_pending_order(self):
        """既に確定済みの注文には二重処理しない。"""
        self.order.status = Order.Status.PAID
        self.order.paid_at = '2026-07-01T00:00:00Z'
        self.order.save()
        payload = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_double',
                    'metadata': {'order_pk': str(self.order.pk)},
                }
            }
        }
        response = self.client.post(
            reverse('orders:stripe_webhook'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        # 二重処理されない（paid_at は変更されない）
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_webhook_unknown_event_ignored(self):
        """未知のイベントは無視される。"""
        payload = {'type': 'payment_intent.created', 'data': {'object': {}}}
        response = self.client.post(
            reverse('orders:stripe_webhook'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)


# =============================================
# PayPal テスト
# =============================================
@override_settings(
    PAYPAL_CLIENT_ID='test-client-id',
    PAYPAL_CLIENT_SECRET='test-client-secret',
    PAYPAL_SANDBOX=True,
)
class PayPalTest(PaymentSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.order = make_payment_order(
            self.user, self.creator, payment_method='paypal'
        )
        OrderItem.objects.create(
            order=self.order, product=self.product,
            product_name='決済テスト素材', product_price=2000,
            quantity=1, subtotal=2000,
        )
        self.client.force_login(self.user)

    @patch('orders.paypal_views.requests.post')
    def test_create_payment_redirects_to_approve(self, mock_post):
        """承認リンクへリダイレクトし、PayPal Order IDを保存。"""
        mock_post.side_effect = [
            # 1回目: OAuthトークン
            SimpleNamespace(
                status_code=200,
                json=lambda: {'access_token': 'TOKEN123'},
                raise_for_status=lambda: None,
            ),
            # 2回目: Order作成
            SimpleNamespace(
                status_code=200,
                json=lambda: {
                    'id': 'PAYPAL-ORDER-001',
                    'links': [
                        {'rel': 'approve', 'href': 'https://www.paypal.com/approve/PAYPAL-ORDER-001'},
                    ],
                },
                raise_for_status=lambda: None,
            ),
        ]
        url = reverse('orders:paypal_create', kwargs={'order_pk': self.order.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, 'https://www.paypal.com/approve/PAYPAL-ORDER-001'
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.paypal_order_id, 'PAYPAL-ORDER-001')

        # 注文作成リクエストの内容検証
        order_call = mock_post.call_args_list[1]
        payload = order_call.kwargs['json']
        self.assertEqual(payload['intent'], 'CAPTURE')
        self.assertEqual(payload['purchase_units'][0]['amount']['value'], '2000.00')
        self.assertEqual(payload['purchase_units'][0]['reference_id'], str(self.order.pk))

    @patch('orders.paypal_views.requests.post')
    def test_capture_completes_order(self, mock_post):
        """Capture成功で注文が確定しダウンロード解放。"""
        mock_post.side_effect = [
            # 1回目: OAuthトークン
            SimpleNamespace(
                status_code=200,
                json=lambda: {'access_token': 'TOKEN123'},
                raise_for_status=lambda: None,
            ),
            # 2回目: Capture
            SimpleNamespace(
                status_code=200,
                json=lambda: {
                    'status': 'COMPLETED',
                    'purchase_units': [{
                        'payments': {'captures': [{'id': 'CAPTURE-001'}]},
                    }],
                },
                raise_for_status=lambda: None,
            ),
        ]
        url = reverse('orders:paypal_capture', kwargs={'order_pk': self.order.pk})
        response = self.client.get(url, {'token': 'PAYPAL-ORDER-001'})
        self.assertRedirects(
            response,
            reverse('orders:order_detail', kwargs={'order_pk': self.order.pk})
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertIsNotNone(self.order.paid_at)
        item = self.order.items.first()
        self.assertTrue(item.is_downloadable)
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, Payment.Status.CONFIRMED)
        self.assertIn('CAPTURE-001', payment.notes)

    @patch('orders.paypal_views.requests.post')
    def test_capture_failed_keeps_pending(self, mock_post):
        """Capture失敗（COMPLETED以外）では注文はPENDINGのまま。"""
        mock_post.side_effect = [
            SimpleNamespace(
                status_code=200,
                json=lambda: {'access_token': 'TOKEN123'},
                raise_for_status=lambda: None,
            ),
            SimpleNamespace(
                status_code=200,
                json=lambda: {'status': 'PAYER_ACTION_REQUIRED'},
                raise_for_status=lambda: None,
            ),
        ]
        url = reverse('orders:paypal_capture', kwargs={'order_pk': self.order.pk})
        response = self.client.get(url, {'token': 'PAYPAL-ORDER-001'})
        self.assertRedirects(
            response,
            reverse('orders:order_detail', kwargs={'order_pk': self.order.pk})
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertFalse(self.order.items.first().is_downloadable)

    @patch('orders.paypal_views.requests.post')
    def test_capture_api_error_keeps_pending(self, mock_post):
        """APIエラー時も注文はPENDINGのまま。"""

        def fake_post(url, **kwargs):
            if 'oauth2/token' in url:
                return SimpleNamespace(
                    status_code=200,
                    json=lambda: {'access_token': 'TOKEN123'},
                    raise_for_status=lambda: None,
                )
            raise requests.exceptions.ConnectionError('network down')

        mock_post.side_effect = fake_post
        url = reverse('orders:paypal_capture', kwargs={'order_pk': self.order.pk})
        response = self.client.get(url, {'token': 'PAYPAL-ORDER-001'})
        self.assertRedirects(
            response,
            reverse('orders:order_detail', kwargs={'order_pk': self.order.pk})
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    @override_settings(PAYPAL_CLIENT_ID='', PAYPAL_CLIENT_SECRET='')
    def test_create_payment_without_keys(self):
        """キー未設定時はエラーメッセージ付きで注文詳細へ。"""
        url = reverse('orders:paypal_create', kwargs={'order_pk': self.order.pk})
        response = self.client.get(url)
        self.assertRedirects(
            response,
            reverse('orders:order_detail', kwargs={'order_pk': self.order.pk})
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
