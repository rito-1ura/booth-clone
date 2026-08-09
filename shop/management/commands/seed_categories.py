"""初期カテゴリ投入コマンド。

使い方:
    python manage.py seed_categories

既に存在するカテゴリはスキップ（冪等）。slug は日本語名そのまま。
"""
from django.core.management.base import BaseCommand

from shop.models import Category

DEFAULT_CATEGORIES = [
    ('イラスト', 'イラスト'),
    ('3Dモデル', '3Dモデル'),
    ('音楽・BGM', '音楽・BGM'),
    ('動画素材', '動画素材'),
    ('ゲーム素材', 'ゲーム素材'),
    ('ツール・ソフト', 'ツール・ソフト'),
    ('書籍・同人誌', '書籍・同人誌'),
    ('その他', 'その他'),
]


class Command(BaseCommand):
    help = '初期カテゴリ（8件）を投入します。既存カテゴリはスキップします。'

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for name, slug in DEFAULT_CATEGORIES:
            _, was_created = Category.objects.get_or_create(
                slug=slug, defaults={'name': name}
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  + {name}'))
            else:
                skipped += 1
        self.stdout.write(
            self.style.SUCCESS(
                f'完了: {created}件作成 / {skipped}件スキップ'
            )
        )
