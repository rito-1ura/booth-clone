import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    display_name = models.CharField(_('display name'), max_length=50)
    avatar = models.ImageField(
        _('avatar'), upload_to='avatars/', blank=True, null=True
    )
    is_email_verified = models.BooleanField(_('email verified'), default=False)
    is_creator = models.BooleanField(_('is creator'), default=False)

    # Use email as the unique identifier for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'display_name']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return self.display_name or self.email


class Creator(models.Model):
    """Extended profile for sellers."""

    class AccountType(models.TextChoices):
        SAVINGS = 'savings', _('普通')
        CHECKING = 'checking', _('当座')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='creator'
    )
    pen_name = models.CharField(_('pen name'), max_length=100)
    profile = models.TextField(_('profile'), blank=True, default='')
    header_image = models.ImageField(
        _('header image'), upload_to='images/', blank=True, null=True
    )
    twitter_url = models.URLField(_('Twitter URL'), blank=True, default='')
    pixiv_url = models.URLField(_('Pixiv URL'), blank=True, default='')
    website_url = models.URLField(_('website URL'), blank=True, default='')
    is_verified = models.BooleanField(_('verified'), default=False)
    total_sales = models.IntegerField(_('total sales'), default=0)
    balance_yen = models.IntegerField(_('balance (yen)'), default=0)

    # Bank account info (encrypted in production)
    bank_name = models.CharField(_('bank name'), max_length=50, blank=True, default='')
    bank_branch = models.CharField(_('branch'), max_length=50, blank=True, default='')
    bank_account_type = models.CharField(
        _('account type'), max_length=10,
        choices=AccountType.choices, blank=True, default=''
    )
    bank_account_number = models.CharField(
        _('account number'), max_length=20, blank=True, default=''
    )
    bank_account_name = models.CharField(
        _('account name'), max_length=100, blank=True, default=''
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('creator')
        verbose_name_plural = _('creators')

    def __str__(self):
        return self.pen_name
