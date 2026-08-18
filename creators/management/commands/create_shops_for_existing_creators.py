"""
creators/management/commands/create_shops_for_existing_creators.py

既にクリエイター登録済みだがショップがないユーザーのために、
自動的にショップを作成する管理コマンド。
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from accounts.models import Creator
from shop.models import Shop


class Command(BaseCommand):
    help = 'ショップを持たないクリエイターにショップを自動作成する'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には作成せず、対象のみ表示する',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        creators_without_shop = Creator.objects.filter(shop__isnull=True)
        count = creators_without_shop.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('ショップを持たないクリエイターはいません。'))
            return

        self.stdout.write(f'対象: {count} 件')

        for creator in creators_without_shop:
            if dry_run:
                self.stdout.write(f'  [DRY RUN] {creator.pen_name} ({creator.user.username}) -> shop作成予定')
                continue

            with transaction.atomic():
                base_slug = slugify(creator.pen_name + 'のショップ') or 'shop'
                slug = base_slug
                counter = 1
                while Shop.objects.filter(slug=slug).exists():
                    slug = f'{base_slug}-{counter}'
                    counter += 1

                Shop.objects.create(
                    creator=creator,
                    name=creator.pen_name + 'のショップ',
                    slug=slug,
                )
                self.stdout.write(f'  Created: {creator.pen_name} -> {slug}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'完了: {count} 件のショップを作成しました。'))
        else:
            self.stdout.write(self.style.WARNING('DRY RUN 完了。--dry-run を外して実行してください。'))