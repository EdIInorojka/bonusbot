# Telegram Funnel Bot (Vercel Only)

FastAPI admin + Telegram WebApp + aiogram webhook.

## 1) Get VERCEL_TOKEN

1. Open https://vercel.com/account/tokens
2. Click `Create Token`
3. Copy token

PowerShell:

```powershell
$env:VERCEL_TOKEN="your_token_here"
```

## 2) ENV

Copy `.env.example` to `.env`.

Quick test (no external services):

- `DATABASE_URL=sqlite+aiosqlite:////tmp/bonuska.db`
- `REDIS_URL=`

Production:

- `DATABASE_URL=postgresql+asyncpg://...`
- `REDIS_URL=redis://...`

Required:

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

Optional for guide-as-message:

- `INSTRUCTION_MESSAGE` (HTML is supported)

## 3) Deploy

```powershell
npx vercel --prod --yes --token $env:VERCEL_TOKEN
```

## 4) Set webhook

```powershell
Invoke-WebRequest -Method POST `
  -Uri "https://<project>.vercel.app/api/telegram/set-webhook" `
  -Body "setup_token=<WEBHOOK_SETUP_TOKEN>"
```

Check:

```powershell
Invoke-WebRequest -Uri "https://<project>.vercel.app/api/telegram/webhook-info?setup_token=<WEBHOOK_SETUP_TOKEN>"
```

## 5) Admin

- Login: `https://<project>.vercel.app/admin/login`
- Content editor: `https://<project>.vercel.app/admin/content`

You can edit texts, photos, buttons, links, subscription channel, and all funnel steps.