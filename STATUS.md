# Status

## Implemented
- Vercel Python entrypoint and routing configuration.
- PostgreSQL support for persistent hosted data, with SQLite local fallback.
- Product catalog, product details, basic guest order creation and tracking.
- Owner login and dashboard for editing product name, price, stock, and active status.
- Optional Telegram text notifications via environment variables.
- Seed products start at Rp1.

## Not implemented
- Real dynamic QRIS or payment gateway.
- Signed webhook validation and payment reconciliation.
- Email notifications.
- Refund workflow, vouchers, reviews, live chat, screenshot receipts, scheduled backups, and full analytics.
- Owner password-change interface, CSRF protection and rate limiting.

Do not treat this MVP as production-ready payment software.


## Vercel fallback note
When `DATABASE_URL` is not configured, the app uses SQLite in `/tmp` so read-only filesystem errors do not prevent startup. This is preview-only and not persistent. Configure PostgreSQL for production.
