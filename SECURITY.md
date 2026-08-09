# セキュリティポリシー

Booth Clone のセキュリティ脆弱性の報告を受け付けています。

## 報告方法

脆弱性を発見した場合は、GitHub の **Security Advisories**（非公開）から報告してください:

1. https://github.com/rito-1ura/booth-clone/security/advisories を開く
2. 「New draft security advisory」で詳細（影響範囲・再現手順・想定される影響）を記入
3. 修正対応まで非公開のまま協力いただきますようお願いします

公開Issueへの脆弱性情報の直接投稿はご遠慮ください。

## 対応方針

- **重大度（Critical/High）**: 報告から72時間以内に修正着手、可能な限り早期に修正版を公開
- **中程度（Medium）**: 7日以内に修正着手
- **軽微（Low）**: 次回リリースに含めて修正

## セキュリティに関する設計方針

- 本番では `DJANGO_DEBUG=false` + `DJANGO_SECURE_COOKIES=true`（Secureクッキー/HSTS）を必須とする
- 外部APIキー（Stripe/PayPal/S3）は環境変数のみで管理し、リポジトリにコミットしない
- 決済はサーバーサイドで検証（Stripe Webhook署名 / PayPal capture API照合）
- 入金確認・ダウンロード解放はクリエイターの明示操作が必要
- レビュー投稿は購入済み（paid）注文の所有者のみ許可
- 出金申請は残高範囲内 + 銀行口座登録済みクリエイターのみ許可（`select_for_update` で二重送信防止）
