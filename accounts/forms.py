from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'username', 'display_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-input'})
        self.fields['email'].widget.attrs.update({'placeholder': 'example@email.com'})
        self.fields['display_name'].widget.attrs.update({'placeholder': '表示名'})
        self.fields['username'].widget.attrs.update({'placeholder': 'ユーザー名（内部用）'})


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('email', 'display_name', 'avatar')
