#!/bin/bash
set -e

echo "== Booth Clone - Docker Entrypoint =="

# Apply migrations
echo "-> Running migrations..."
python manage.py migrate --noinput

# Create initial categories (if not exists)
echo "-> Creating initial data..."
python manage.py shell -c "
from shop.models import Category
categories = ['イラスト', '3Dモデル', '音楽・BGM', '動画素材', 'ゲーム素材', 'ツール・ソフト', '書籍・同人誌', 'その他']
for i, name in enumerate(categories):
    Category.objects.get_or_create(name=name, slug=name, sort_order=i)
print(f'== {Category.objects.count()} categories ready ==')
"

# Compile locale messages
echo "-> Compiling translations..."
python manage.py compilemessages --noinput 2>/dev/null || true

# Collect static files
echo "-> Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser only when explicitly configured via environment
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "-> Creating superuser from environment..."
  python manage.py shell -c "
from accounts.models import User
email = '$DJANGO_SUPERUSER_EMAIL'
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        email=email,
        username=email.split('@')[0],
        display_name='管理者',
        password='$DJANGO_SUPERUSER_PASSWORD',
    )
    print(f'== Superuser created: {email} ==')
else:
    print('== Superuser already exists ==')
"
else
  echo "-> DJANGO_SUPERUSER_EMAIL/PASSWORD not set; skipping superuser creation"
fi

echo "== Setup complete. Starting Gunicorn... =="
exec gunicorn booth.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
