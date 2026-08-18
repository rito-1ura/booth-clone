"""
accounts/backends.py — Email-based authentication backend.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    メールアドレスでログインできる認証バックエンド。
    USERNAME_FIELD = 'email' に対応。
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # username または email のいずれかで認証を試行
        if username is None:
            username = kwargs.get('username') or kwargs.get('email')
        
        if username is None or password is None:
            return None

        # emailで検索
        try:
            user = User.objects.get(**{f'{User.USERNAME_FIELD}__iexact': username})
        except User.DoesNotExist:
            # usernameでも検索
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                User().set_password(password)
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None