from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('products/', views.product_list_view, name='product_list'),
    path('category/<str:category_slug>/', views.product_list_view, name='product_list_by_category'),
    path('product/<uuid:pk>/', views.product_detail_view, name='product_detail'),
    path('product/<uuid:pk>/review/', views.review_create_view, name='review_create'),
    path('product/<uuid:pk>/favorite/', views.favorite_toggle_view, name='favorite_toggle'),
    path('favorites/', views.favorite_list_view, name='favorites'),
    path('shop/<str:slug>/', views.shop_page_view, name='shop_page'),
]
