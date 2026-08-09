from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.models import Creator
from .models import Category, Shop, Product, ProductImage, Review
from orders.models import Order, OrderItem

User = get_user_model()


class CategoryModelTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='イラスト', slug='illust')

    def test_category_creation(self):
        self.assertEqual(str(self.cat), 'イラスト')
        self.assertTrue(self.cat.is_active)

    def test_category_tree(self):
        child = Category.objects.create(
            name='デジタルイラスト',
            slug='digital-illust',
            parent=self.cat,
        )
        self.assertEqual(child.parent, self.cat)


class ProductModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='c@example.com', username='c',
            display_name='c', password='p1234'
        )
        self.creator = Creator.objects.create(user=self.user, pen_name='工房')
        self.shop = Shop.objects.create(
            creator=self.creator, name='工房の店', slug='kobo'
        )
        self.cat = Category.objects.create(name='イラスト', slug='illust')
        self.product = Product.objects.create(
            creator=self.creator,
            shop=self.shop,
            category=self.cat,
            name='テストイラスト集',
            description='説明文です',
            price=1200,
            stock_quantity=None,
            is_public=True,
        )

    def test_product_creation(self):
        self.assertEqual(str(self.product), 'テストイラスト集')
        self.assertEqual(self.product.price, 1200)

    def test_product_type_default(self):
        self.assertEqual(self.product.product_type, 'digital')

    def test_product_url(self):
        url = reverse('shop:product_detail', kwargs={'pk': self.product.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_product_list_view(self):
        url = reverse('shop:product_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'テストイラスト集')

    def test_product_list_by_category(self):
        url = reverse('shop:product_list_by_category',
                       kwargs={'category_slug': 'illust'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'テストイラスト集')

    def test_home_view(self):
        url = reverse('shop:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_public_product_hidden(self):
        self.product.is_public = False
        self.product.save()
        url = reverse('shop:product_detail', kwargs={'pk': self.product.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='b@example.com', username='b',
            display_name='b', password='p1234'
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
            name='BGM集', description='desc', price=500, is_public=True,
        )
        self.order = Order.objects.create(
            user=self.user,
            order_number='TEST-001',
            total_amount=500,
            payment_method='bank_transfer',
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name='BGM集',
            product_price=500,
            quantity=1,
            subtotal=500,
        )

    def test_create_review(self):
        review = Review.objects.create(
            product=self.product,
            user=self.user,
            order=self.order,
            rating=5,
            comment='素晴らしい！',
        )
        self.assertEqual(str(review), 'BGM集 - ★5 by b')
        self.assertTrue(review.is_public)

    def test_unique_review_constraint(self):
        Review.objects.create(
            product=self.product,
            user=self.user,
            order=self.order,
            rating=4,
        )
        with self.assertRaises(Exception):
            Review.objects.create(
                product=self.product,
                user=self.user,
                order=self.order,
                rating=3,
            )
