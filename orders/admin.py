from django.contrib import admin
from django.utils.html import format_html
from .models import Cart, CartItem, Order, OrderItem, Payment, DownloadLog, Withdrawal


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1
    readonly_fields = ('added_at',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'created_at')
    search_fields = ('user__email', 'session_key')
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ('product_name', 'product_price', 'subtotal')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'user', 'total_amount', 'status',
        'payment_method', 'created_at'
    )
    list_filter = ('status', 'payment_method')
    search_fields = ('order_number', 'user__email')
    readonly_fields = ('order_number', 'total_amount', 'created_at')
    inlines = [OrderItemInline]
    actions = ['mark_as_paid']

    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='paid', paid_at=timezone.now())
        self.message_user(request, f'{updated} 件の注文を「入金確認済」に更新しました。')
    mark_as_paid.short_description = '選択した注文を「入金確認済」にする'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'payment_method', 'amount', 'status', 'confirmed_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('order__order_number',)
    readonly_fields = ('created_at',)


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = ('order_item', 'user', 'ip_address', 'downloaded_at')
    list_filter = ('downloaded_at',)
    search_fields = ('user__email', 'ip_address')


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('creator', 'amount', 'status', 'created_at', 'processed_at')
    list_filter = ('status',)
    search_fields = ('creator__pen_name',)
