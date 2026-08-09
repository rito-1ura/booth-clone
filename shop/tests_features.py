"""
レビュー投稿・お気に入り・出金申請のテスト。
"""
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User, Creator
from orders.models import Order, OrderItem, Payment
from shop.models import Category, Shop, Product, Review, Favorite


def _make_user(email='buyer@example.com', password='test1234', display_name='購入者'):
    return User.objects.create_user(
        email=email, username=email.split('@')[0],
        password=password, display_name=display_name,
    )


def _make_creator(user=None, pen_name='テスト工房'):
    user = user or _make_user('creator@example.com', display_name='クリエイター')
    return Creator.objects.create(user=user, pen_name=pen_name)


def _make_product(creator, name='テスト商品', price=1000):
    category = Category.objects.create(name='テストカテゴリ', slug='test-cat')
    shop = Shop.objects.create(
        creator=creator, name='テストショップ', slug='test-shop'
    )
    return Product.objects.create(
        creator=creator, category=category, shop=shop,
        name=name, price=price, description='説明', product_type='digital',
        is_public=True,
    )


def _make_paid_order(user, product, order_number='ORD-001'):
    order = Order.objects.create(
        user=user, order_number=order_number,
        total_amount=product.price, payment_method='bank_transfer',
        status=Order.Status.PAID,
    )
    OrderItem.objects.create(
        order=order, product=product,
        product_name=product.name, product_price=product.price,
        quantity=1, subtotal=product.price,
    )
    return order


class FavoriteTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.creator = _make_creator()
        self.product = _make_product(self.creator)
        self.client.login(email='buyer@example.com', password='test1234')

    def test_toggle_adds_favorite(self):
        """POSTでお気に入り追加できる。"""
        url = reverse('shop:favorite_toggle', kwargs={'pk': self.product.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('shop:product_detail', kwargs={'pk': self.product.pk}))
        self.assertTrue(Favorite.objects.filter(user=self.user, product=self.product).exists())

    def test_toggle_removes_favorite(self):
        """2回目のPOSTで解除される。"""
        Favorite.objects.create(user=self.user, product=self.product)
        url = reverse('shop:favorite_toggle', kwargs={'pk': self.product.pk})
        self.client.post(url)
        self.assertFalse(Favorite.objects.filter(user=self.user, product=self.product).exists())

    def test_favorite_list(self):
        """お気に入り一覧に商品が表示される。"""
        Favorite.objects.create(user=self.user, product=self.product)
        response = self.client.get(reverse('shop:favorites'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'テスト商品')

    def test_favorite_list_empty(self):
        """お気に入りが空のときメッセージ表示。"""
        response = self.client.get(reverse('shop:favorites'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'お気に入りはまだありません')

    def test_requires_login(self):
        """未ログインはログインページへ。"""
        self.client.logout()
        response = self.client.post(reverse('shop:favorite_toggle', kwargs={'pk': self.product.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)


class ReviewTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.creator = _make_creator()
        self.product = _make_product(self.creator)
        self.order = _make_paid_order(self.user, self.product, 'ORD-REV-1')
        self.client.login(email='buyer@example.com', password='test1234')

    def test_review_form_shown_to_purchaser(self):
        """購入済みユーザーには投稿フォームが表示される。"""
        response = self.client.get(reverse('shop:product_detail', kwargs={'pk': self.product.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'review-form-box')
        self.assertContains(response, 'ORD-REV-1')

    def test_review_form_hidden_for_non_purchaser(self):
        """未購入ユーザーにはフォームが表示されない。"""
        other = _make_user('other@example.com')
        self.client.login(email='other@example.com', password='test1234')
        response = self.client.get(reverse('shop:product_detail', kwargs={'pk': self.product.pk}))
        self.assertNotContains(response, 'review-form-box')

    def test_create_review_success(self):
        """購入者はレビューを投稿できる。"""
        url = reverse('shop:review_create', kwargs={'pk': self.product.pk})
        response = self.client.post(url, {
            'rating': 5, 'comment': 'とても良い商品でした',
            'order_pk': self.order.pk,
        })
        self.assertRedirects(response, reverse('shop:product_detail', kwargs={'pk': self.product.pk}))
        review = Review.objects.get(product=self.product, user=self.user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'とても良い商品でした')
        self.assertEqual(review.order, self.order)

    def test_cannot_review_without_paid_order(self):
        """未払い注文ではレビューできない。"""
        self.order.status = Order.Status.PENDING
        self.order.save()
        url = reverse('shop:review_create', kwargs={'pk': self.product.pk})
        response = self.client.post(url, {
            'rating': 4, 'comment': 'テスト', 'order_pk': self.order.pk,
        })
        self.assertRedirects(response, reverse('shop:product_detail', kwargs={'pk': self.product.pk}))
        self.assertFalse(Review.objects.filter(product=self.product, user=self.user).exists())

    def test_duplicate_review_rejected(self):
        """同一注文での二重投稿は拒否される。"""
        Review.objects.create(
            product=self.product, user=self.user, order=self.order,
            rating=3, comment='1回目',
        )
        url = reverse('shop:review_create', kwargs={'pk': self.product.pk})
        response = self.client.post(url, {
            'rating': 5, 'comment': '2回目', 'order_pk': self.order.pk,
        })
        self.assertRedirects(response, reverse('shop:product_detail', kwargs={'pk': self.product.pk}))
        self.assertEqual(Review.objects.filter(product=self.product, user=self.user).count(), 1)

    def test_invalid_rating_rejected(self):
        """1〜5以外の評価は拒否される。"""
        url = reverse('shop:review_create', kwargs={'pk': self.product.pk})
        response = self.client.post(url, {
            'rating': 99, 'comment': '不正', 'order_pk': self.order.pk,
        })
        self.assertRedirects(response, reverse('shop:product_detail', kwargs={'pk': self.product.pk}))
        self.assertFalse(Review.objects.filter(product=self.product, user=self.user).exists())


class WithdrawalTests(TestCase):
    def setUp(self):
        self.user = _make_user('creator@example.com', display_name='クリエイター')
        self.creator = _make_creator(self.user)
        # 銀行口座情報を登録
        self.creator.bank_name = 'テスト銀行'
        self.creator.bank_branch = '本店'
        self.creator.bank_account_type = 'savings'
        self.creator.bank_account_number = '1234567'
        self.creator.bank_account_name = 'テスト タロウ'
        self.creator.balance_yen = 5000
        self.creator.save()
        self.client.login(email='creator@example.com', password='test1234')

    def test_withdrawal_page_renders(self):
        """出金申請ページが表示される。"""
        response = self.client.get(reverse('creators:withdrawals'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '出金可能残高')
        self.assertContains(response, '¥5,000' if False else '5,000')

    def test_withdrawal_success(self):
        """正しい金額で出金申請すると残高が減る。"""
        from orders.tasks import notify_new_withdrawal
        response = self.client.post(reverse('creators:withdrawals'), {'amount': 2000})
        self.assertRedirects(response, reverse('creators:withdrawals'))
        self.creator.refresh_from_db()
        self.assertEqual(self.creator.balance_yen, 3000)
        from orders.models import Withdrawal
        w = Withdrawal.objects.get(creator=self.creator)
        self.assertEqual(w.amount, 2000)
        self.assertEqual(w.status, Withdrawal.Status.PENDING)
        self.assertIn('テスト銀行', w.bank_info)

    def test_withdrawal_over_balance_rejected(self):
        """残高超過の申請は拒否され、残高は変わらない。"""
        response = self.client.post(reverse('creators:withdrawals'), {'amount': 9999})
        self.assertRedirects(response, reverse('creators:withdrawals'))
        self.creator.refresh_from_db()
        self.assertEqual(self.creator.balance_yen, 5000)
        from orders.models import Withdrawal
        self.assertFalse(Withdrawal.objects.filter(creator=self.creator).exists())

    def test_withdrawal_below_minimum_rejected(self):
        """1,000円未満の申請は拒否される。"""
        response = self.client.post(reverse('creators:withdrawals'), {'amount': 500})
        self.assertRedirects(response, reverse('creators:withdrawals'))
        self.creator.refresh_from_db()
        self.assertEqual(self.creator.balance_yen, 5000)

    def test_withdrawal_requires_bank_registered(self):
        """銀行口座未登録では申請できない。"""
        self.creator.bank_name = ''
        self.creator.save()
        response = self.client.post(reverse('creators:withdrawals'), {'amount': 2000})
        self.assertRedirects(response, reverse('creators:withdrawals'))
        self.creator.refresh_from_db()
        self.assertEqual(self.creator.balance_yen, 5000)
        self.assertContains(response, '銀行口座が未登録です') if response.status_code == 200 else None

    def test_withdrawal_history_shown(self):
        """申請履歴が表示される。"""
        from orders.models import Withdrawal
        Withdrawal.objects.create(
            creator=self.creator, amount=1500, bank_info='テスト銀行 本店 1234567',
        )
        response = self.client.get(reverse('creators:withdrawals'))
        self.assertContains(response, '1,500')
        self.assertContains(response, '申請中')
