from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.db import transaction
from django.utils import timezone
import csv
from django.http import HttpResponse
from accounts.models import Creator
from shop.models import Product, ProductImage, ProductTag, Category
from orders.models import Order, OrderItem, Payment, Withdrawal
from orders.tasks import notify_payment_confirmed, notify_new_withdrawal


def _get_creator(user):
    """Helper: get creator or redirect."""
    if not hasattr(user, 'creator'):
        return None
    return user.creator


def _day_range(day):
    """ローカル日付の開始〜終了（UTC aware datetime）を返す。

    日次集計は `paid_at__date=day` ではなく範囲比較を使う。
    （DBではpaid_at__dateはUTC日付で評価されるため、JST深夜に
     前日分が欠落/混入するバグを回避する）
    """
    from datetime import datetime
    start = timezone.make_aware(
        datetime.combine(day, datetime.min.time()),
        timezone.get_current_timezone(),
    )
    end = start + timezone.timedelta(days=1)
    return start, end


@login_required
def dashboard_view(request):
    """Creator dashboard — sales summary, pending orders, stock alerts."""
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    # Today's summary
    today = timezone.localdate()
    day_start, day_end = _day_range(today)

    # Orders requiring attention
    pending_orders = Order.objects.filter(
        items__product__creator=creator,
        status=Order.Status.PENDING
    ).distinct().select_related('user')[:10]

    # Paid orders today
    today_sales = Order.objects.filter(
        items__product__creator=creator,
        paid_at__gte=day_start,
        paid_at__lt=day_end,
        status__in=[Order.Status.PAID, Order.Status.SHIPPED, Order.Status.COMPLETED]
    ).aggregate(
        total=Sum('total_amount'),
        count=Count('id')
    )

    # Stock alerts
    low_stock_products = Product.objects.filter(
        creator=creator,
        is_public=True,
        stock_quantity__lte=5,
        product_type='physical'
    ).exclude(stock_quantity__isnull=True)[:10]

    # Recent sales chart data (last 7 days, local date 기준)
    daily_sales = []
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        ds, de = _day_range(day)
        day_total = Order.objects.filter(
            items__product__creator=creator,
            paid_at__gte=ds,
            paid_at__lt=de,
            status__in=[Order.Status.PAID, Order.Status.SHIPPED, Order.Status.COMPLETED]
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        daily_sales.append({
            'date': day.strftime('%m/%d'),
            'total': day_total,
        })

    context = {
        'creator': creator,
        'pending_orders': pending_orders,
        'today_sales_amount': today_sales['total'] or 0,
        'today_orders_count': today_sales['count'] or 0,
        'low_stock_products': low_stock_products,
        'daily_sales': daily_sales,
        'unpaid_count': pending_orders.count(),
    }
    return render(request, 'creators/dashboard.html', context)


@login_required
def product_list_view(request):
    """Creator's product management."""
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    products = Product.objects.filter(creator=creator).select_related('category')
    return render(request, 'creators/product_list.html', {'products': products})


@login_required
def product_create_view(request):
    """Create a new product."""
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', 0)
        category_id = request.POST.get('category')
        product_type = request.POST.get('product_type', 'digital')
        stock_quantity = request.POST.get('stock_quantity') or None

        if not name or not description or not price:
            messages.error(request, '必須項目を入力してください。')
        else:
            try:
                price = int(price)
                if price <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, '価格は正の整数で入力してください。')
                return render(request, 'creators/product_form.html', {
                    'categories': Category.objects.filter(is_active=True),
                })

            with transaction.atomic():
                product = Product.objects.create(
                    creator=creator,
                    shop=creator.shop,
                    category_id=category_id,
                    name=name,
                    description=description,
                    price=price,
                    product_type=product_type,
                    stock_quantity=stock_quantity if product_type == 'physical' else None,
                )

                # Handle main image
                if 'main_image' in request.FILES:
                    ProductImage.objects.create(
                        product=product,
                        image=request.FILES['main_image'],
                        is_main=True,
                        sort_order=0,
                    )

                # Handle additional images
                for image_file in request.FILES.getlist('extra_images'):
                    ProductImage.objects.create(
                        product=product,
                        image=image_file,
                        sort_order=1,
                    )

            messages.success(request, f'「{product.name}」を作成しました。')
            return redirect('creators:product_list')

    return render(request, 'creators/product_form.html', {
        'categories': Category.objects.filter(is_active=True),
    })


@login_required
def order_management_view(request):
    """Order management with payment confirmation."""
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    status_filter = request.GET.get('status', '')

    orders = Order.objects.filter(
        items__product__creator=creator
    ).distinct().select_related('user').prefetch_related('items')

    if status_filter:
        orders = orders.filter(status=status_filter)

    orders = orders.order_by('-created_at')

    return render(request, 'creators/order_management.html', {
        'orders': orders,
        'current_status': status_filter,
    })


@login_required
def confirm_payment_view(request, order_pk):
    """Mark an order as paid and release downloads."""
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    order = get_object_or_404(Order, pk=order_pk)
    # Verify this order contains one of the creator's products
    if not OrderItem.objects.filter(order=order, product__creator=creator).exists():
        messages.error(request, 'この注文はあなたの商品ではありません。')
        return redirect('creators:order_management')

    if order.status != Order.Status.PENDING:
        messages.warning(request, 'この注文は既に処理済みです。')
        return redirect('creators:order_management')

    with transaction.atomic():
        order.status = Order.Status.PAID
        order.paid_at = timezone.now()
        order.save(update_fields=['status', 'paid_at'])

        # Release all creator's items in this order for download
        OrderItem.objects.filter(
            order=order, product__creator=creator
        ).update(is_downloadable=True)

        # Update payment record
        Payment.objects.filter(order=order).update(
            status=Payment.Status.CONFIRMED,
            confirmed_by=request.user,
            confirmed_at=timezone.now(),
        )

        # Update creator balance
        creator.balance_yen += order.total_amount
        creator.save(update_fields=['balance_yen'])

    messages.success(
        request,
        f'注文 {order.order_number} の入金を確認しました。ダウンロードを解放しました。'
    )
    # Notify buyer via Celery
    notify_payment_confirmed.delay(order.pk)
    return redirect('creators:order_management')


@login_required
def sales_report_view(request):
    """Sales reports by period and product."""
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    period = request.GET.get('period', '30')

    try:
        days = int(period)
    except ValueError:
        days = 30

    since = timezone.now() - timezone.timedelta(days=days)

    # Sales by product
    product_sales = OrderItem.objects.filter(
        order__status__in=[
            Order.Status.PAID, Order.Status.SHIPPED, Order.Status.COMPLETED
        ],
        product__creator=creator,
        order__paid_at__gte=since,
    ).values(
        'product_name'
    ).annotate(
        total_qty=Sum('quantity'),
        total_sales=Sum('subtotal'),
        order_count=Count('order', distinct=True),
    ).order_by('-total_sales')

    total_revenue = sum(item['total_sales'] for item in product_sales)

    context = {
        'product_sales': product_sales,
        'total_revenue': total_revenue,
        'period': days,
        'period_label': f'過去{days}日間' if days > 1 else '本日',
    }
    return render(request, 'creators/sales_report.html', context)


@login_required
def export_orders_csv(request):
    """CSVエクスポート: 注文一覧"""
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    orders = Order.objects.filter(
        items__product__creator=creator
    ).distinct().select_related('user').order_by('-created_at')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="orders_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        '注文番号', '購入者', 'メールアドレス', '合計金額',
        '決済方法', 'ステータス', '注文日', '入金確認日'
    ])
    for order in orders:
        writer.writerow([
            order.order_number,
            order.user.display_name,
            order.user.email,
            order.total_amount,
            order.get_payment_method_display(),
            order.get_status_display(),
            order.created_at.strftime('%Y/%m/%d %H:%M'),
            order.paid_at.strftime('%Y/%m/%d %H:%M') if order.paid_at else '',
        ])
    return response


@login_required
def export_sales_csv(request):
    """CSVエクスポート: 売上レポート"""
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    period = request.GET.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30
    since = timezone.now() - timezone.timedelta(days=days)

    product_sales = OrderItem.objects.filter(
        order__status__in=[
            Order.Status.PAID, Order.Status.SHIPPED, Order.Status.COMPLETED
        ],
        product__creator=creator,
        order__paid_at__gte=since,
    ).values(
        'product_name'
    ).annotate(
        total_qty=Sum('quantity'),
        total_sales=Sum('subtotal'),
        order_count=Count('order', distinct=True),
    ).order_by('-total_sales')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="sales_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['商品名', '販売数', '注文数', '売上'])
    for item in product_sales:
        writer.writerow([
            item['product_name'],
            item['total_qty'],
            item['order_count'],
            item['total_sales'],
        ])
    return response


@login_required
def withdrawal_view(request):
    """出金申請 — 残高から金額を指定して申請する。

    - 銀行口座情報（Creator.bank_*）が未登録なら登録ページへ誘導
    - 申請成功時: Withdrawal作成 + balance_yen減算 + 管理者通知
    - 同一ページに申請履歴（一覧）を表示
    """
    creator = _get_creator(request.user)
    if not creator:
        return redirect('accounts:become_creator')

    withdrawals = Withdrawal.objects.filter(
        creator=creator
    ).order_by('-created_at')[:20]

    bank_registered = bool(
        creator.bank_name and creator.bank_account_number
        and creator.bank_account_name
    )

    if request.method == 'POST':
        try:
            amount = int(request.POST.get('amount', '0'))
        except ValueError:
            amount = 0
        if amount < 1000:
            messages.error(request, '出金金額は1,000円以上で指定してください。')
        elif amount > creator.balance_yen:
            messages.error(
                request,
                f'出金可能残高（¥{creator.balance_yen:,}）を超えています。'
            )
        elif not bank_registered:
            messages.error(request, '先に銀行口座情報を登録してください。')
        else:
            # スナップショットを作成して申請
            bank_info = (
                f'{creator.bank_name} {creator.bank_branch} '
                f'（{creator.get_bank_account_type_display()}） '
                f'{creator.bank_account_number} {creator.bank_account_name}'
            )
            with transaction.atomic():
                # 二重送信対策: 残高を再検証
                creator = Creator.objects.select_for_update().get(pk=creator.pk)
                if amount > creator.balance_yen:
                    messages.error(request, '出金可能残高を超えています。')
                    return redirect('creators:withdrawals')
                withdrawal = Withdrawal.objects.create(
                    creator=creator,
                    amount=amount,
                    bank_info=bank_info,
                )
                creator.balance_yen -= amount
                creator.save(update_fields=['balance_yen'])
            notify_new_withdrawal.delay(withdrawal.pk)
            messages.success(
                request,
                f'出金申請（¥{amount:,}）を受け付けました。処理完了までお待ちください。'
            )
        return redirect('creators:withdrawals')

    context = {
        'creator': creator,
        'withdrawals': withdrawals,
        'bank_registered': bank_registered,
    }
    return render(request, 'creators/withdrawals.html', context)
