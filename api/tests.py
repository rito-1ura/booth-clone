from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from accounts.models import Creator
from shop.models import Category, Shop, Product
from orders.models import Order

User = get_user_model()


class APISetUpMixin:
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='api@example.com', username='apiuser',
            display_name='APIユーザー', password='p1234'
        )
        self.creator_user = User.objects.create_user(
            email='creator@example.com', username='apicreator',
            display_name='API出品者', password='p1234'
        )
        self.creator = Creator.objects.create(
            user=self.creator_user, pen_name='API工房'
        )
        self.shop = Shop.objects.create(
            creator=self.creator, name='API店', slug='api-mise'
        )
        self.cat = Category.objects.create(name='イラスト', slug='api-illust')
        self.product = Product.objects.create(
            creator=self.creator, shop=self.shop, category=self.cat,
            name='APIテスト商品', description='APIテスト用の商品です',
            price=2000, is_public=True, is_in_stock=True,
        )


class PublicAPIEndpointsTest(APISetUpMixin, TestCase):
    def test_products_list(self):
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], 'APIテスト商品')
        self.assertEqual(response.data['results'][0]['price'], 2000)

    def test_product_detail(self):
        response = self.client.get(f'/api/products/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'APIテスト商品')
        self.assertIn('category', response.data)
        self.assertIn('creator', response.data)

    def test_product_search(self):
        response = self.client.get('/api/products/?search=テスト')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_product_filter_by_category(self):
        response = self.client.get(f'/api/products/?category__slug={self.cat.slug}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_categories_list(self):
        response = self.client.get('/api/categories/')
        self.assertEqual(response.status_code, 200)
        names = [c['name'] for c in response.data['results']]
        self.assertIn('イラスト', names)

    def test_shops_list(self):
        response = self.client.get('/api/shops/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['slug'], 'api-mise')

    def test_popular_products(self):
        response = self.client.get('/api/products/popular/')
        self.assertEqual(response.status_code, 200)

    def test_new_arrivals(self):
        response = self.client.get('/api/products/new_arrivals/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_non_public_product_hidden_from_api(self):
        self.product.is_public = False
        self.product.save()
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)


class AuthenticatedAPIEndpointsTest(APISetUpMixin, TestCase):
    def test_anonymous_cannot_access_cart(self):
        response = self.client.get('/api/cart/')
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_access_orders(self):
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, 403)

    def test_token_auth_cart_access(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get('/api/cart/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['items'], [])

    def test_cart_add_item(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.post(
            '/api/cart/add/',
            {'product': str(self.product.pk), 'quantity': 2},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['quantity'], 2)
        self.assertEqual(response.data['total'], 4000)

    def test_cart_remove_item(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.client.post(
            '/api/cart/add/',
            {'product': str(self.product.pk), 'quantity': 1},
            format='json',
        )
        cart_response = self.client.get('/api/cart/')
        item_pk = cart_response.data['items'][0]['id']
        response = self.client.post(
            '/api/cart/remove/', {'item': item_pk}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['items'], [])

    def test_orders_list(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        Order.objects.create(
            user=self.user,
            order_number='API-ORDER-001',
            total_amount=2000,
            payment_method='bank_transfer',
        )
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['order_number'], 'API-ORDER-001')

    def test_users_me_only(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['email'], 'api@example.com')
