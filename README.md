# Elian Store — Vercel-ready starter

This project has a Vercel Python entrypoint (`api/index.py`) and `vercel.json`.

## Important: persistent database is required
Vercel serverless functions do not provide a reliable persistent local filesystem. For a real store, create a managed PostgreSQL database (for example, Neon) and add its connection string as `DATABASE_URL` in Vercel Project Settings → Environment Variables. Use the provider's pooled connection string if recommended by the provider. Without `DATABASE_URL`, the app now uses `/tmp/elian_store_preview.db` on Vercel so the page can start, but that database is temporary and may be lost between invocations/deployments. Use PostgreSQL for persistent production data.

## Deploy
1. Extract the ZIP.
2. Upload the project to a private GitHub repository.
3. In Vercel, choose **Add New → Project**, import that repository, and deploy.
4. In Vercel Project Settings → Environment Variables, add:
   - `FLASK_SECRET_KEY`: long random secret
   - `OWNER_USERNAME`: `owner223`
   - `OWNER_PASSWORD`: `owner224` (change it before public use)
   - `DATABASE_URL`: hosted PostgreSQL connection URL
   - `TELEGRAM_BOT_TOKEN`: token newly rotated via BotFather
   - `TELEGRAM_OWNER_CHAT_ID`: `1121940843`
   - `TELEGRAM_CHANNEL_CHAT_ID`: `@eliansuz` if the channel is public and bot has posting permission
   - `COOKIE_SECURE`: `1`
5. Redeploy after adding variables.
6. Open `/health` and confirm database reports `postgres`.
7. Open `/login` and check the owner dashboard.

The first app startup initializes tables and seeds the five products at Rp1. If the database already contains products, it does not overwrite them.

## Telegram security
The previous bot token was exposed and is intentionally not included in this ZIP. Revoke/rotate it in BotFather and use the new token only as a Vercel environment variable. Never put it in source code or a public repository.

## Payment status
This version does **not** implement real QRIS/dynamic QRIS, gateway webhook verification, email, automatic refunds, live chat, image upload, scheduled backup, or full reporting. Checkout creates a pending order only. Do not accept real payments or mark orders paid until a legitimate merchant gateway and signed server-side webhooks have been implemented and tested.

## Local development
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```
Open `http://127.0.0.1:5000`. Local SQLite is used when `DATABASE_URL` is empty.
