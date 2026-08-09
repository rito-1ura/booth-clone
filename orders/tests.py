from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.models import Creator
from shop.models import Category, Shop, Product
from .models import Cart, CartItem, Order, OrderItem, Payment, DownloadLog

User = get_user_model()


class CartTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='u@example.com', username='u',
            display_name='u', password='p1234'
        )
        self.creator = Creator.objects.create(
            user=self.user, pen_name='工房'
        )
        self.shop = Shop.objects.create(
            creator=self.creator, name='店', slug='mise'
        )
        self.cat = Category.objects.create(name='音楽', slug='music')
        self.product = Product.objects.create(
            creator=self.creator, shop=self.shop, category=self.cat,
            name='BGM素材', description='desc', price=800,
            is_public=True, is_in_stock=True,
        )

    def test_add_to_cart_anonymous(self):
        url = reverse('orders:cart_add', kwargs={'product_pk': self.product.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('orders:cart_detail'))

    def test_cart_detail_view(self):
        url = reverse('orders:cart_detail')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_cart_item_subtotal(self):
        cart = Cart.objects.create(session_key='test-key')
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.assertEqual(item.subtotal(), 1600)


class OrderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='buyer@example.com', username='buyer',
            display_name='購入者', password='p1234'
        )
        self.creator_user = User.objects.create_user(
            email='seller@example.com', username='seller',
            display_name='出品者', password='p1234'
        )
        self.creator = Creator.objects.create(
            user=self.creator_user, pen_name='作品工房'
        )
        self.shop = Shop.objects.create(
            creator=self.creator, name='工房', slug='kobo-1'
        )
        self.cat = Category.objects.create(name='素材', slug='sozai')
        self.product = Product.objects.create(
            creator=self.creator, shop=self.shop, category=self.cat,
            name='デジタル素材集', description='desc', price=1500,
            is_public=True, is_in_stock=True,
        )

    def test_create_order(self):
        order = Order.objects.create(
            user=self.user,
            order_number='BO-20260731-001',
            total_amount=1500,
            payment_method='bank_transfer',
        )
        self.assertEqual(str(order), 'BO-20260731-001')
        self.assertEqual(order.status, 'pending')

    def test_order_with_items(self):
        order = Order.objects.create(
            user=self.user,
            order_number='BO-20260731-002',
            total_amount=1500,
            payment_method='bank_transfer',
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name='デジタル素材集',
            product_price=1500,
            quantity=1,
            subtotal=1500,
        )
        self.assertEqual(item.product_name, 'デジタル素材集')
        self.assertFalse(item.is_downloadable)

    def test_payment_creation(self):
        order = Order.objects.create(
            user=self.user,
            order_number='BO-20260731-003',
            total_amount=1500,
            payment_method='bank_transfer',
        )
        payment = Payment.objects.create(
            order=order,
            payment_method='bank_transfer',
            amount=1500,
        )
        self.assertEqual(str(payment), f'Payment for {order.order_number}')
        self.assertEqual(payment.status, 'pending')

    def test_download_log(self):
        order = Order.objects.create(
            user=self.user,
            order_number='BO-20260731-004',
            total_amount=1500,
            payment_method='bank_transfer',
        )
        item = OrderItem.objects.create(
            order=order, product=self.product,
            product_name='素材', product_price=1500,
            quantity=1, subtotal=1500,
        )
        log = DownloadLog.objects.create(
            order_item=item,
            user=self.user,
            ip_address='127.0.0.1',
        )
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_order_list_requires_login(self):
        url = reverse('orders:order_history')
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f'/accounts/login/?next={url}'
        )

    def test_checkout_requires_login(self):
        url = reverse('orders:checkout')
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f'/accounts/login/?next={url}'
        )

    def test_full_checkout_flow(self):
        """Test complete checkout flow with logged-in user."""
        self.client.login(email='buyer@example.com', password='p1234')

        # Add to cart
        cart_url = reverse('orders:cart_add',
                           kwargs={'product_pk': self.product.pk})
        self.client.post(cart_url)

        # Check cart has item
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)

        # Go to checkout
        checkout_url = reverse('orders:checkout')
        response = self.client.post(checkout_url, {
            'payment_method': 'bank_transfer',
        })
        # Should redirect to order complete
        self.assertEqual(response.status_code, 302)

        # Verify order was created
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_amount, 1500)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.payment_method, 'bank_transfer')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product_name, 'デジタル素材集')

        # Verify payment record
        self.assertTrue(hasattr(order, 'payment'))
        self.assertEqual(order.payment.amount, 1500)

        # Verify cart is now empty
        self.assertEqual(cart.items.count(), 0)
