from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('cart/', views.cart_detail_view, name='cart_detail'),
    path('cart/add/<uuid:product_pk>/', views.cart_add_view, name='cart_add'),
    path('cart/remove/<uuid:item_pk>/', views.cart_remove_view, name='cart_remove'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('complete/<uuid:order_pk>/', views.order_complete_view, name='order_complete'),
    path('history/', views.order_history_view, name='order_history'),
    path('detail/<uuid:order_pk>/', views.order_detail_view, name='order_detail'),
    path('download/<uuid:item_pk>/', views.download_view, name='download'),

    # Stripe決済
    path('stripe/create-session/<uuid:order_pk>/',
         views.create_stripe_checkout_session, name='stripe_create_session'),
    path('stripe/success/<uuid:order_pk>/',
         views.stripe_success_view, name='stripe_success'),
    path('stripe/webhook/',
         views.stripe_webhook_view, name='stripe_webhook'),

    # PayPal決済
    path('paypal/create/<uuid:order_pk>/',
         views.create_paypal_payment, name='paypal_create'),
    path('paypal/capture/<uuid:order_pk>/',
         views.capture_paypal_payment, name='paypal_capture'),
]
