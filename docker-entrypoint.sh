#!/bin/bash
set -e

echo "🚀 Booth Clone — Docker Entrypoint"

# Apply migrations
echo "→ Running migrations..."
python manage.py migrate --noinput

# Create initial categories (if not exists)
echo "→ Creating initial data..."
python manage.py shell -c "
from shop.models import Category
categories = ['イラスト', '3Dモデル', '音楽・BGM', '動画素材', 'ゲーム素材', 'ツール・ソフト', '書籍・同人誌', 'その他']
for i, name in enumerate(categories):
    Category.objects.get_or_create(name=name, slug=name, sort_order=i)
print(f'✅ {Category.objects.count()} categories ready')
"

# Compile locale messages
echo "→ Compiling translations..."
python manage.py compilemessages --noinput 2>/dev/null || true

# Collect static files
echo "→ Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if not exists
python manage.py shell -c "
from accounts.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        email='admin@booth.local',
        username='admin',
        display_name='管理者',
        password='admin1234'
    )
    print('✅ Default superuser created: admin@booth.local / admin1234')
else:
    print('✅ Superuser already exists')
"

echo "✅ Setup complete. Starting Gunicorn..."
exec gunicorn booth.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
