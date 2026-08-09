# Booth Clone 運用マニュアル

本マニュアルは Booth Clone の日常運用・障害対応・設定変更の手順書です。
対象: サイト運営者（管理者）およびクリエイター（出品者）。

---

## 1. 日常運用フロー

### 1.1 銀行振込・コンビニ・PayPay注文の入金確認

1. 管理画面（`/admin/`）またはクリエイターダッシュボード（`/creators/dashboard/`）を開く
2. 「未入金注文（要対応）」に新規注文がないか確認する
3. 銀行口座・PayPayIDへの入金を確認する（振込人名義と注文者を照合）
4. 「入金確認」ボタンをクリック → 注文が「入金確認済」になり、購入者にダウンロードが解放される
5. 購入者には確認メールが自動送信される

> **重要**: 入金を確認してから「入金確認」を押してください。誤って押した場合は
> Django Admin で注文ステータスを `pending` に戻し、ダウンロード解放を解除できます
> （注文詳細 → ステータス変更 → 各注文商品の `is_downloadable` をオフ）。

### 1.2 ダウンロード解放

- デジタル商品: 入金確認で自動解放（購入者の注文履歴からダウンロード可能に）
- ダウンロード可能回数は商品設定の `download_limit`（デフォルト無制限）
- ダウンロード履歴は管理画面（DownloadLog）で確認可能

### 1.3 物理商品の発送

1. 注文管理（`/creators/orders/`）で「発送済み」にする
2. 購入者に発送通知メールが自動送信される
3. 配送追跡番号がある場合は注文メモに記録する

### 1.4 売上確認とCSVエクスポート

- 売上レポート（`/creators/sales-report/`）: 期間別（7/30/90日/1年）の売上・商品別構成比
- CSVダウンロード: 売上CSV（商品別集計）・注文CSV（明細）をUTF-8 BOM付きで出力（Excelで開ける）
- 日次売上グラフはダッシュボードにSVGで表示

---

## 2. 出品フロー（クリエイター向け）

1. アカウント登録 → 「出品する」からクリエイター登録（ペンネーム入力）
2. ショップを作成（ショップ名・スラッグ）
3. 商品を出品:
   - 商品名・説明・カテゴリ・価格（税込）
   - 種別: デジタル（ファイルアップロード + ファイルサイズ） / 物理（在庫数）
   - サムネイル画像（任意・複数可）
4. 公開設定をONにして公開

> 商品のファイルは `media/`（またはS3バケット）に保存されます。

---

## 3. 決済設定

### 3.1 銀行振込（デフォルト・無料）

- 振込先口座情報はテンプレート `templates/orders/checkout.html` と
  `templates/orders/order_detail.html` の bank-info ブロックで管理
- 入金確認は手動（§1.1）

### 3.2 Stripe（クレジットカード・手数料あり）

1. https://dashboard.stripe.com/apikeys でキーを取得（本番はLiveキー）
2. 環境変数を設定:
   ```
   STRIPE_PUBLISHABLE_KEY=pk_live_xxx
   STRIPE_SECRET_KEY=sk_live_xxx
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   ```
3. Webhook設定: Stripeダッシュボード → Webhooks → エンドポイント追加
   - URL: `https://<ドメイン>/orders/stripe/webhook/`
   - イベント: `checkout.session.completed`
4. チェックアウトで「クレジットカード (Stripe)」を選ぶと自動決済されます

### 3.3 PayPal（手数料あり）

1. https://developer.paypal.com/dashboard/applications でアプリを作成
2. 環境変数を設定:
   ```
   PAYPAL_CLIENT_ID=xxx
   PAYPAL_CLIENT_SECRET=xxx
   PAYPAL_SANDBOX=True   # テスト時。本番は False
   ```
3. サンドボックステスト:
   - サンドボックスアカウント（Buyer）で購入 → PayPalの承認ページ → 承認 → 自動確定
   - テストは `manage.py test orders.test_payments` でAPIキーなしでも実施可能（モック）

### 3.4 サンドボックスでの動作確認手順

1. サンドボックスキーでサーバー起動（`PAYPAL_SANDBOX=True`）
2. 商品をカート → チェックアウト → PayPalを選択
3. PayPalの承認ページでサンドボックス購入者アカウントでログイン
4. 承認後、注文が自動的に「入金確認済」になりダウンロードが解放されることを確認
5. Stripeも同様に `stripe checkout` のテストカード `4242 4242 4242 4242` で確認

---

## 4. バックアップ

### 4.1 データベース

```bash
# PostgreSQL
pg_dump -U postgres booth > backup_$(date +%Y%m%d).sql

# SQLite（開発時）
cp db.sqlite3 backup_$(date +%Y%m%d).sqlite3
```

### 4.2 メディアファイル

```bash
# ローカル保存の場合
tar czf media_$(date +%Y%m%d).tar.gz media/

# S3（R2/B2）保存の場合
# バケット側のバージョニング機能を利用するか、rcloneで定期同期
rclone sync s3:booth-media backup:booth-media
```

### 4.3 推奨運用

- DB: 日次バックアップ（cron）
- メディア: 週次バックアップ
- バックアップはサイトとは別のストレージに保存する（3-2-1ルール）

### 4.4 出金申請の処理（管理者）

1. クリエイターが出金申請すると、出金一覧（`/admin/orders/withdrawal/`）に「申請中」で表示され、管理者へメール通知される
2. 申請内容（金額・振込先スナップショット）を確認し、実際に振込を行う
3. 振込完了後、管理画面でステータスを「完了」に変更（`processed_at` が自動記録）
4. 残高不足・口座情報不備などで振込できない場合は「却下」に変更 → 申請額がクリエイターの残高へ自動戻し

> **重要**: 出金申請時点で残高は減算済みです。却下時のみ残高に戻ります。
> 完了にした場合の残高戻しは行われないため、二重振込に注意してください。

### 4.5 レビュー・お気に入り（購入者向け機能）

- **レビュー投稿**: 入金確認済み（paid）注文の購入者のみ投稿可。商品詳細ページの「レビューを書く」フォームから、評価（1〜5）＋コメント＋対象注文を選択
- **お気に入り**: ログインユーザーは商品詳細のハートボタンで登録/解除。一覧は `/favorites/` で確認
- 不適切なレビューは Django Admin で `is_public=False` にすると非表示化（一覧・平均評価から除外）

---

## 5. 障害対応

### 5.1 サイトが応答しない

1. サーバープロセス確認: `docker compose ps`（Docker運用時）
2. ログ確認: `docker compose logs -f app`
3. 再起動: `docker compose restart app`
4. それでも復旧しない場合: `docker compose down && docker compose up -d --build`

### 5.2 メールが届かない

1. `.env` の `EMAIL_*` 設定を確認（TLS/ポート）
2. Celeryワーカーが起動しているか確認（`docker compose ps` で celery-worker が Up か）
3. テスト送信: `manage.py shell` から
   ```python
   from django.core.mail import send_mail
   send_mail('test', 'body', 'noreply@your-domain', ['you@example.com'])
   ```

### 5.3 決済の不整合（入金したのに解放されない）

1. 注文管理画面で対象注文を開く
2. Paymentレコードの状態を確認（`pending` のままなら未確認）
3. 銀行振込なら入金を確認して「入金確認」を実行
4. Stripe/PayPalなら決済ダッシュボード側で完了を確認し、未完了ならWebhook設定を見直す
5. どうしても手動で確定する場合: Django Admin で注文ステータスを `paid` に変更し、
   各注文商品の `is_downloadable` を ON にする

### 5.4 ダウンロードができない

1. 注文ステータスが `paid` か確認
2. 商品ファイル（`media/` またはS3）が存在するか確認
3. S3使用時はバケットの公開設定と署名バージョン（s3v4）を確認
4. ダウンロード回数上限に達していないか確認（`download_limit`）

### 5.5 Redis ダウン（Celeryが動かない）

- `CELERY_TASK_ALWAYS_EAGER=True` にするとメール送信が同期実行になり、Redisなしでも動きます
- 本番では Redis の死活監視を推奨

---

## 6. セキュリティチェックリスト

- [ ] `DJANGO_SECRET_KEY` を強力なランダム値に設定（本番）
- [ ] `DJANGO_DEBUG=False`（本番）
- [ ] `DJANGO_ALLOWED_HOSTS` に実ドメインのみ許可
- [ ] `DJANGO_CSRF_TRUSTED_ORIGINS` に実ドメインを設定（例: `https://example.com`）
- [ ] `DJANGO_SECURE_COOKIES=true`（Secureクッキー + HSTS。Caddy配下で）
- [ ] 本番は PostgreSQL + HTTPS（TLS終端）で運用
- [ ] Stripe/PayPalはLiveキーを `.env` にのみ保持（リポジトリにコミットしない）
- [ ] `SECRET_KEY` ・DBパスワードはリポジトリ外で管理
- [ ] `DJANGO_SUPERUSER_EMAIL/PASSWORD` は初期作成後に削除・パスワード変更
- [ ] 不要なスーパーユーザーは削除
- [ ] 定期的に `pip-audit` または Dependabot で依存関係の脆弱性確認
- [ ] S3バケットはプライベート設定（配信は署名付きURL経由）

---

## 7. アプリ構成

```
accounts/  ユーザー認証・クリエイター登録・プロフィール
shop/      商品・カテゴリ・ショップ・トップページ
orders/    カート・注文・決済（Stripe/PayPal）・ダウンロード・Celeryタスク
creators/  ダッシュボード・出品管理・注文管理・売上レポート・CSV
api/       DRF REST API（モバイル連携）
```

Celeryタスク（`orders/tasks.py`）:

| タスク | トリガー | 内容 |
|---|---|---|
| `send_order_confirmation_email` | 注文作成 | 注文確認メール |
| `notify_payment_confirmed` | 入金確認 | 入金確認メール |
| `notify_new_withdrawal` | 出金申請 | 管理者への通知 |
