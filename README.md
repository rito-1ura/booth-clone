# Booth Clone

個人クリエイター向けの販売プラットフォーム（Booth風）。ダークテーマ（`#0C0C0F` / アクセント `#818CF8`）のモダンなUIで、デジタル商品・物理商品を販売できます。

**基本方針: 完全無料で運用できること**
- 銀行振込・コンビニ・PayPay送金は手動入金確認（手数料ゼロ）
- クレジットカード（Stripe）・PayPal はオプション（決済手数料のみ）
- 外部API・ストレージはすべて無料枠のもののみ使用

---

## 機能一覧

| 機能 | 説明 |
|---|---|
| ショッピング | 商品一覧・カテゴリ絞り込み・検索・ランキング・お気に入り・共有 |
| カート / 注文 | セッションベースのカート、注文履歴、注文詳細 |
| 決済 | 銀行振込（手動確認）・コンビニ・PayPay・Stripe・PayPal |
| クリエイター | 出品管理・注文管理・入金確認（ワンクリックでダウンロード解放）・売上レポート・CSVエクスポート |
| ダッシュボード | 売上推移（SVGグラフ）・統計カード・未入金注文 |
| REST API | DRF + Token認証（モバイルアプリ連携用） |
| ストレージ | ローカル or S3互換（Cloudflare R2 / Backblaze B2 / MinIO） |
| CI/CD | GitHub Actions（テスト + DockerイメージをGHCRへ自動push） |
| 管理画面 | Django Admin（日本語化済み・101翻訳） |

## 技術スタック

- Python 3.11 / Django 5.2
- データベース: PostgreSQL（開発時はSQLiteフォールバック）
- Celery + Redis（メール通知。テスト時は `CELERY_TASK_ALWAYS_EAGER` でRedis不要）
- DRF（djangorestframework + django-filter + Token認証）
- Stripe / PayPal（REST v2、サンドボックス対応）
- django-storages（S3互換）
- Docker Compose（app / db / redis / celery-worker / celery-beat）

## セットアップ（Windows + Git Bash）

### 1. 依存関係のインストール

```bash
# uv を使用（推奨）
uv venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

# または venv 直接
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

> Git Bash では `source .venv/bin/activate` は使えません。常に `.venv/Scripts/python.exe` を直接呼び出してください。
> Hermes 環境では `PYTHONPATH=` を頭に付けてクリアしてください（`PYTHONPATH=` を付けるとシステム側のsite-packagesと衝突しません）。

### 2. 環境変数

```bash
cp .env.example .env
```

`.env` は Django が自動読み込みしません。Git Bash で使う場合は:

```bash
export $(cat .env | xargs)   # 開発時のみ
```

または環境変数を直接設定してください（一覧は下部参照）。

### 3. マイグレーションと初期データ

```bash
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed_categories        # カテゴリ8件投入
.venv/Scripts/python.exe manage.py createsuperuser
.venv/Scripts/python.exe manage.py compilemessages        # 日本語化（django.mo生成）
```

### 4. 起動

```bash
.venv/Scripts/python.exe manage.py runserver 0.0.0.0:8000
```

- サイト: http://localhost:8000/
- 管理画面: http://localhost:8000/admin/
- API ドキュメント: http://localhost:8000/api/

### 5. テスト

```bash
.venv/Scripts/python.exe manage.py test --noinput
# 54件（accounts / shop / orders / orders.test_payments / api）
```

決済テスト（Stripe/PayPal）は `unittest.mock` で外部APIをモックしており、**APIキーなしで実行可能**です。

## 環境変数一覧

| 変数 | 必須 | 説明 |
|---|---|---|
| `DJANGO_SECRET_KEY` | 本番必須 | Djangoシークレットキー |
| `DJANGO_DEBUG` | - | `True`/`False`（デフォルトTrue） |
| `DJANGO_ALLOWED_HOSTS` | 本番必須 | カンマ区切り（デフォルト `localhost,127.0.0.1`） |
| `DATABASE_URL` | 本番必須 | `postgresql://user:pass@host:5432/dbname`。未設定ならSQLite |
| `EMAIL_BACKEND` / `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_USE_TLS` / `DEFAULT_FROM_EMAIL` | 本番必須 | メール通知設定 |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | 本番必須 | `redis://redis:6379/0` |
| `CELERY_TASK_ALWAYS_EAGER` | - | `True`でRedisなし同期実行（テスト・開発用デフォルト） |
| `STRIPE_PUBLISHABLE_KEY` / `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | オプション | Stripe決済。取得: https://dashboard.stripe.com/apikeys |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` / `PAYPAL_SANDBOX` | オプション | PayPal決済。取得: https://developer.paypal.com/dashboard/applications |
| `USE_S3` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_STORAGE_BUCKET_NAME` / `AWS_S3_ENDPOINT_URL` / `AWS_S3_REGION_NAME` | オプション | S3互換ストレージ（R2/B2/MinIO） |

### S3互換ストレージ（完全無料の選択肢）

| サービス | 無料枠 | 備考 |
|---|---|---|
| **Cloudflare R2** | 10GB / エグレス無料 | 最推奨。`AWS_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com` |
| **Backblaze B2** | 10GB / 月1GBエグレス | 旧`S3_API_URL`推奨 |
| **MinIO** | 自己ホスト | 自前サーバーなら完全無料 |

S3有効時はファイル配信が署名付きURL（5分有効）になります。

## Docker Compose 運用

```bash
cp .env.example .env    # 実値を記入
docker compose up -d --build
```

5サービス: `app`（gunicorn）/ `db`（postgres:16）/ `redis` / `celery-worker` / `celery-beat`。
`docker-entrypoint.sh` が migrate → 初期カテゴリ → collectstatic → gunicorn を自動実行します。

## REST API 一覧

ベースURL: `/api/`（Token認証: `Authorization: Token <key>` ヘッダー。トークンは管理画面または `rest_framework.authtoken` で発行）

| エンドポイント | メソッド | 認証 | 説明 |
|---|---|---|---|
| `/api/products/` | GET | 不要 | 商品一覧（`?search=` `?category=` `?ordering=`） |
| `/api/products/popular/` | GET | 不要 | 人気商品 |
| `/api/products/new_arrivals/` | GET | 不要 | 新着商品 |
| `/api/products/{id}/` | GET | 不要 | 商品詳細 |
| `/api/categories/` | GET | 不要 | カテゴリ一覧 |
| `/api/shops/` | GET | 不要 | ショップ一覧 |
| `/api/cart/` | GET/POST/DELETE | 要Token | カート操作 |
| `/api/orders/` | GET | 要Token | 注文履歴 |
| `/api/users/` | GET | 要Token | ユーザー一覧（本人情報のみ） |
| `/api/auth/` | GET/POST | - | DRFログイン（ブラウズ可能API用） |

## CI/CD

`.github/workflows/ci.yml`:

1. **test job**: Python 3.11 + 依存インストール → `manage.py check` → 全テスト → `compilemessages`
2. **docker job**: test成功後、Buildx + Actionsキャッシュでイメージをビルドし **GHCRへpush**（ブランチ / `v*`タグ / SHA の3タグ）

## ライセンス

Apache License 2.0
