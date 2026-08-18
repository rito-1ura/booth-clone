"""
booth/pages.py — 静的ページ（利用規約・プライバシー・特定商取引法・ガイド・FAQ・サポート）とお問い合わせ。
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings

from .forms import ContactForm


def _static_page(request, template, title):
    return render(request, template, {'page_title': title})


def terms_view(request):
    return _static_page(request, 'pages/terms.html', '利用規約')


def privacy_view(request):
    return _static_page(request, 'pages/privacy.html', 'プライバシーポリシー')


def legal_view(request):
    return _static_page(request, 'pages/legal.html', '特定商取引法表示')


def guide_view(request):
    return _static_page(request, 'pages/guide.html', '販売ガイド')


def faq_view(request):
    return _static_page(request, 'pages/faq.html', 'よくある質問')


def support_view(request):
    return _static_page(request, 'pages/support.html', 'サポート')


def contact_view(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        name = form.cleaned_data['name']
        email = form.cleaned_data['email']
        subject = form.cleaned_data['subject']
        body = form.cleaned_data['message']
        send_mail(
            f'[お問い合わせ] {subject}',
            f'お名前: {name}\nメール: {email}\n\n{body}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=False,
        )
        messages.success(request, 'お問い合わせを送信しました。担当者よりご連絡いたします。')
        return redirect('contact')
    return render(request, 'pages/contact.html', {'form': form})
