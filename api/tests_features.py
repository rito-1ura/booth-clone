"""
API拡張（お気に入り・レビュー投稿・出金申請）のテスト。
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from accounts.models import Creator
from shop.models import Category, Shop, Product, Review, Favorite
from orders.models import Order, OrderItem, Withdrawal

User = get_user_model()


class APISetUpMixin:
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='buyer@example.com', username='buyer',
            display_name='購入者', password='p1234'
        )
        self.token = Token.objects.create(user=self.user)
        self.creator_user = User.objects.create_user(
            email='creator@example.com', username='apicreator',
            display_name='API出品者', password='p1234'
        )
        self.creator_token = Token.objects.create(user=self.creator_user)
        self.creator = Creator.objects.create(
            user=self.creator_user, pen_name='API工房'
        )
        self.shop = Shop.objects.create(
            creator=self.creator, name='API店', slug='api-mise-2'
        )
        self.cat = Category.objects.create(name='イラスト', slug='api-illust-2')
        self.product = Product.objects.create(
            creator=self.creator, shop=self.shop, category=self.cat,
            name='APIテスト商品', description='APIテスト用の商品です',
            price=2000, is_public=True, is_in_stock=True,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')


class FavoriteAPITests(APISetUpMixin, TestCase):
    def test_requires_auth(self):
        self.client.credentials()
        response = self.client.get('/api/favorites/')
        self.assertEqual(response.status_code, 403)

    def test_add_favorite(self):
        response = self.client.post('/api/favorites/add/', {'product': self.product.pk})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Favorite.objects.filter(user=self.user, product=self.product).exists())

    def test_add_duplicate_returns_200(self):
        Favorite.objects.create(user=self.user, product=self.product)
        response = self.client.post('/api/favorites/add/', {'product': self.product.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 1)

    def test_add_nonexistent_product_404(self):
        response = self.client.post(
            '/api/favorites/add/',
            {'product': '00000000-0000-0000-0000-000000000000'},
        )
        self.assertEqual(response.status_code, 404)

    def test_list_favorites(self):
        Favorite.objects.create(user=self.user, product=self.product)
        response = self.client.get('/api/favorites/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['product']['name'], 'APIテスト商品')

    def test_remove_favorite(self):
        Favorite.objects.create(user=self.user, product=self.product)
        response = self.client.post('/api/favorites/remove/', {'product': self.product.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Favorite.objects.filter(user=self.user).exists())

    def test_toggle_add_and_remove(self):
        response = self.client.post('/api/favorites/toggle/', {'product': self.product.pk})
        self.assertEqual(response.data['favorited'], True)
        response = self.client.post('/api/favorites/toggle/', {'product': self.product.pk})
        self.assertEqual(response.data['favorited'], False)
        self.assertFalse(Favorite.objects.filter(user=self.user).exists())

    def test_cannot_favorite_other_users_products(self):
        """他人のお気に入りは見えない。"""
        other = User.objects.create_user(
            email='other@example.com', username='other',
            display_name='他ユーザー', password='p1234'
        )
        Favorite.objects.create(user=other, product=self.product)
        response = self.client.get('/api/favorites/')
        self.assertEqual(len(response.data), 0)


class ReviewPostAPITests(APISetUpMixin, TestCase):
    def _make_paid_order(self):
        order = Order.objects.create(
            user=self.user, order_number='API-ORD-1',
            total_amount=self.product.price,
            payment_method='bank_transfer', status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=order, product=self.product,
            product_name=self.product.name, product_price=self.product.price,
            quantity=1, subtotal=self.product.price,
        )
        return order

    def test_requires_auth(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/products/{self.product.pk}/reviews/',
            {'rating': 5, 'comment': 'いいね'},
        )
        # IsAuthenticatedOrReadOnly により未認証の書き込みは 403（既存APIと同様）
        self.assertEqual(response.status_code, 403)

    def test_non_purchaser_forbidden(self):
        response = self.client.post(
            f'/api/products/{self.product.pk}/reviews/',
            {'rating': 5, 'comment': 'まだ買ってない'},
        )
        self.assertEqual(response.status_code, 403)

    def test_post_review_success(self):
        order = self._make_paid_order()
        response = self.client.post(
            f'/api/products/{self.product.pk}/reviews/',
            {'rating': 5, 'comment': 'とても良かった', 'order_pk': order.pk},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['rating'], 5)
        self.assertEqual(response.data['user_name'], '購入者')
        review = Review.objects.get(product=self.product, user=self.user)
        self.assertEqual(review.order, order)

    def test_invalid_rating_400(self):
        self._make_paid_order()
        response = self.client.post(
            f'/api/products/{self.product.pk}/reviews/',
            {'rating': 99, 'comment': '不正'},
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_review_400(self):
        order = self._make_paid_order()
        Review.objects.create(
            product=self.product, user=self.user, order=order,
            rating=3, comment='1回目',
        )
        response = self.client.post(
            f'/api/products/{self.product.pk}/reviews/',
            {'rating': 5, 'comment': '2回目', 'order_pk': order.pk},
        )
        self.assertEqual(response.status_code, 400)

    def test_reviews_get_still_works(self):
        response = self.client.get(f'/api/products/{self.product.pk}/reviews/')
        self.assertEqual(response.status_code, 200)


class WithdrawalAPITests(APISetUpMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.creator.bank_name = 'テスト銀行'
        self.creator.bank_branch = '本店'
        self.creator.bank_account_type = 'savings'
        self.creator.bank_account_number = '1234567'
        self.creator.balance_yen = 5000
        self.creator.save()

    def test_non_creator_forbidden(self):
        response = self.client.post('/api/withdrawals/', {'amount': 2000})
        self.assertEqual(response.status_code, 403)

    def test_requires_auth(self):
        self.client.credentials()
        response = self.client.get('/api/withdrawals/')
        self.assertEqual(response.status_code, 403)

    def test_create_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.creator_token.key}')
        response = self.client.post('/api/withdrawals/', {'amount': 2000})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['amount'], 2000)
        self.assertEqual(response.data['status_display'], '申請中')
        self.creator.refresh_from_db()
        self.assertEqual(self.creator.balance_yen, 3000)
        withdrawal = Withdrawal.objects.get(creator=self.creator)
        self.assertIn('テスト銀行', withdrawal.bank_info)

    def test_no_bank_account_400(self):
        self.creator.bank_name = ''
        self.creator.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.creator_token.key}')
        response = self.client.post('/api/withdrawals/', {'amount': 2000})
        self.assertEqual(response.status_code, 400)
        self.creator.refresh_from_db()
        self.assertEqual(self.creator.balance_yen, 5000)

    def test_below_minimum_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.creator_token.key}')
        response = self.client.post('/api/withdrawals/', {'amount': 500})
        self.assertEqual(response.status_code, 400)
        self.creator.refresh_from_db()
        self.assertEqual(self.creator.balance_yen, 5000)

    def test_over_balance_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.creator_token.key}')
        response = self.client.post('/api/withdrawals/', {'amount': 99999})
        self.assertEqual(response.status_code, 400)
        self.creator.refresh_from_db()
        self.assertEqual(self.creator.balance_yen, 5000)

    def test_list_history(self):
        Withdrawal.objects.create(
            creator=self.creator, amount=1500,
            bank_info='テスト銀行 本店 1234567',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.creator_token.key}')
        response = self.client.get('/api/withdrawals/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['amount'], 1500)

    def test_user_without_creator_sees_empty_list(self):
        response = self.client.get('/api/withdrawals/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
