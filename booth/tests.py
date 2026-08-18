"""
booth/tests.py — 静的ページ（サポート・利用規約・プライバシー・特定商取引・ガイド・FAQ）とお問い合わせフォームのテスト。
"""
from django.test import TestCase
from django.core import mail
from django.urls import reverse


class StaticPageTests(TestCase):
    def test_support_page(self):
        response = self.client.get(reverse('support'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'サポート')
        self.assertContains(response, 'よくある質問')

    def test_terms_page(self):
        response = self.client.get(reverse('terms'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '利用規約')
        self.assertContains(response, '第1条')

    def test_privacy_page(self):
        response = self.client.get(reverse('privacy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'プライバシーポリシー')
        self.assertContains(response, '収集する情報')

    def test_legal_page(self):
        response = self.client.get(reverse('legal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '特定商取引法')
        self.assertContains(response, '販売業者')
        self.assertContains(response, '返品・返金')

    def test_guide_page(self):
        response = self.client.get(reverse('guide'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '販売ガイド')
        self.assertContains(response, '3.4%')

    def test_faq_page(self):
        response = self.client.get(reverse('faq'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'よくある質問')
        self.assertContains(response, 'ダウンロード')


class ContactFormTests(TestCase):
    def test_contact_page_renders_form(self):
        response = self.client.get(reverse('contact'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'お問い合わせ')
        self.assertContains(response, 'form-input')

    def test_contact_submit_success_sends_mail(self):
        response = self.client.post(reverse('contact'), {
            'name': 'テスト太郎',
            'email': 'taro@example.com',
            'subject': '商品について',
            'message': '商品の動作環境を教えてください。',
        })
        self.assertRedirects(response, reverse('contact'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('商品について', mail.outbox[0].subject)
        self.assertIn('テスト太郎', mail.outbox[0].body)

    def test_contact_submit_invalid(self):
        response = self.client.post(reverse('contact'), {
            'name': '',
            'email': 'invalid-email',
            'subject': '',
            'message': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
