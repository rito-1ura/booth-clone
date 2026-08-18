"""
booth/forms.py — サイト共通フォーム（お問い合わせ）。
"""
from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(
        label='お名前',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'お名前',
        }),
    )
    email = forms.EmailField(
        label='メールアドレス',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'example@email.com',
        }),
    )
    subject = forms.CharField(
        label='件名',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '件名を入力',
        }),
    )
    message = forms.CharField(
        label='お問い合わせ内容',
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 6,
            'placeholder': 'お問い合わせ内容をご記入ください',
        }),
    )
