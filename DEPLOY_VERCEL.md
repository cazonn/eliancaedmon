# Checklist deployment Vercel

- [ ] Upload project to private GitHub repository.
- [ ] Create managed PostgreSQL database.
- [ ] Add `DATABASE_URL` in Vercel environment variables.
- [ ] Set a long random `FLASK_SECRET_KEY`.
- [ ] Change the initial owner password before public transactions.
- [ ] Rotate Telegram bot token; do not reuse the exposed token.
- [ ] Set Telegram variables if notifications are wanted.
- [ ] Deploy and open `/health`.
- [ ] Test login, product price edits, order creation and tracking.
- [ ] Do not enable real payments before gateway integration is complete.
