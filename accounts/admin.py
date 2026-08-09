from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Creator


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {
            'fields': ('display_name', 'avatar', 'is_email_verified', 'is_creator')
        }),
        (_('Permissions'), {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            ),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'display_name', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'display_name', 'is_creator', 'is_active', 'is_staff')
    list_filter = ('is_creator', 'is_active', 'is_staff')
    search_fields = ('email', 'display_name')
    ordering = ('email',)


@admin.register(Creator)
class CreatorAdmin(admin.ModelAdmin):
    list_display = ('pen_name', 'user', 'is_verified', 'total_sales', 'balance_yen')
    list_filter = ('is_verified',)
    search_fields = ('pen_name', 'user__email')
    readonly_fields = ('total_sales', 'balance_yen', 'created_at')
