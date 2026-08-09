from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            display_name='テスト太郎',
            password='testpass1234',
        )

    def test_create_user(self):
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertEqual(self.user.display_name, 'テスト太郎')
        self.assertFalse(self.user.is_creator)
        self.assertFalse(self.user.is_email_verified)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email='admin@example.com',
            username='admin',
            display_name='管理者',
            password='adminpass1234',
        )
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)

    def test_email_unique(self):
        with self.assertRaises(Exception):
            User.objects.create_user(
                email='test@example.com',
                username='testuser2',
                display_name='重複',
                password='pass1234',
            )

    def test_str_returns_display_name(self):
        self.assertEqual(str(self.user), 'テスト太郎')

    def test_str_fallback_to_email(self):
        user = User.objects.create_user(
            email='nobody@example.com',
            username='nobody',
            display_name='',
            password='pass1234',
        )
        # display_nameが空文字の場合、emailにフォールバック
        self.assertEqual(str(user), 'nobody@example.com')


class CreatorModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='creator@example.com',
            username='creator',
            display_name='クリエイター花子',
            password='pass1234',
        )

    def test_create_creator(self):
        from accounts.models import Creator
        creator = Creator.objects.create(
            user=self.user,
            pen_name='クリエイティブ工房',
        )
        self.assertEqual(creator.pen_name, 'クリエイティブ工房')
        self.assertEqual(str(creator), 'クリエイティブ工房')
        self.assertEqual(creator.balance_yen, 0)
        self.assertFalse(creator.is_verified)

    def test_creator_one_to_one(self):
        from accounts.models import Creator
        Creator.objects.create(user=self.user, pen_name='作品工房')
        # Creatorが既に存在する場合は取得できる
        self.assertTrue(hasattr(self.user, 'creator'))
        self.assertEqual(self.user.creator.pen_name, '作品工房')
