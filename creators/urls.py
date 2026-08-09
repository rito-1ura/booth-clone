from django.urls import path
from . import views

app_name = 'creators'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('products/', views.product_list_view, name='product_list'),
    path('products/create/', views.product_create_view, name='product_create'),
    path('orders/', views.order_management_view, name='order_management'),
    path('orders/<uuid:order_pk>/confirm-payment/', views.confirm_payment_view, name='confirm_payment'),
    path('sales-report/', views.sales_report_view, name='sales_report'),
    path('export/orders/', views.export_orders_csv, name='export_orders'),
    path('export/sales/', views.export_sales_csv, name='export_sales'),
    path('withdrawals/', views.withdrawal_view, name='withdrawals'),
]
