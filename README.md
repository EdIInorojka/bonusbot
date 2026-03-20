# Telegram Funnel Bot (Vercel)

FastAPI admin + aiogram webhook + Telegram WebApp.

## 1) Get `VERCEL_TOKEN`

1. Open https://vercel.com/account/tokens
2. Click `Create Token`
3. Copy token

```powershell
$env:VERCEL_TOKEN="your_token_here"
```

## 2) Configure persistent storage

For stable work on Vercel use:

- `Postgres` for users/settings/steps/links/texts
- `Vercel Blob` for images

### Postgres

Connect any Vercel-supported Postgres provider (Neon/Supabase/Aurora) and set:

- `DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB_NAME`

Do not use `sqlite` in `/tmp` for production.

### Blob

Create Blob store in Vercel and set:

- `BLOB_READ_WRITE_TOKEN=...`
- `BLOB_PREFIX=media` (optional folder prefix)

## 3) ENV

Copy `.env.example` to `.env` and fill required values:

- `BOT_TOKEN`
- `BOT_USERNAME`
- `BOT_MODE=webhook`
- `WEB_BASE_URL=https://<project>.vercel.app`
- `WEBHOOK_BASE_URL=https://<project>.vercel.app`
- `TELEGRAM_WEBHOOK_SECRET`
- `WEBHOOK_SETUP_TOKEN`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_SESSION_SECRET`
- `DATABASE_URL` (Postgres)

Optional:

- `REDIS_URL`
- `POSTBACK_PATH` (default: `/api/postback/event`)
- `POSTBACK_SECRET`
- `REGISTRATION_PROMO_CODE` (default: `HUNTCASH`)
- `REGISTRATION_PROMO_PARAM` (default: `promocode`)
- `INSTRUCTION_MESSAGE` (Telegram HTML)

## 4) Deploy

```powershell
npx vercel --prod --yes --token $env:VERCEL_TOKEN
```

## 5) Set webhook

```powershell
Invoke-WebRequest -Method POST `
  -Uri "https://<project>.vercel.app/api/telegram/set-webhook" `
  -Body "setup_token=<WEBHOOK_SETUP_TOKEN>"
```

Check:

```powershell
Invoke-WebRequest -Uri "https://<project>.vercel.app/api/telegram/webhook-info?setup_token=<WEBHOOK_SETUP_TOKEN>"
```

## 6) Admin

- Login: `https://<project>.vercel.app/admin/login`
- Content: `https://<project>.vercel.app/admin/content`
- Media: `https://<project>.vercel.app/admin/media`
- Settings: `https://<project>.vercel.app/admin/settings`

In `Settings` you can:

- see if DB is persistent or ephemeral
- clean users
- clean content (links/steps/media)
- run full cleanup

## 7) Registration callbacks (postback)

Endpoints:

- `https://<project>.vercel.app/api/postback/event`
- `https://<project>.vercel.app/api/postback/registration`
- `https://<project>.vercel.app/api/postback/first-deposit`

Example:

```text
https://<project>.vercel.app/api/postback/registration?source_id={source_id}&event=registration&secret=<POSTBACK_SECRET>
```
