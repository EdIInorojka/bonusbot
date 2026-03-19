# Telegram Funnel Bot (Vercel Only)

Проект работает на Vercel: FastAPI admin + Telegram WebApp + aiogram webhook.

## 1) Где взять VERCEL_TOKEN

1. Открой https://vercel.com/account/tokens
2. Нажми `Create Token`
3. Скопируй токен

PowerShell:

```powershell
$env:VERCEL_TOKEN="your_token_here"
```

## 2) ENV переменные

Скопируй `.env.example` в `.env`.

### Вариант A: быстрый тест без внешних сервисов

- `DATABASE_URL=sqlite+aiosqlite:////tmp/bonuska.db`
- `REDIS_URL=` (пусто)

### Вариант B: нормальный прод

- `DATABASE_URL=postgresql+asyncpg://...`
- `REDIS_URL=redis://...`

Обязательно в обоих вариантах:

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

## 3) Деплой

```powershell
npx vercel --prod --yes --token $env:VERCEL_TOKEN
```

## 4) Установка webhook

```powershell
Invoke-WebRequest -Method POST `
  -Uri "https://<project>.vercel.app/api/telegram/set-webhook" `
  -Body "setup_token=<WEBHOOK_SETUP_TOKEN>"
```

Проверка:

```powershell
Invoke-WebRequest -Uri "https://<project>.vercel.app/api/telegram/webhook-info?setup_token=<WEBHOOK_SETUP_TOKEN>"
```

## 5) Админка

- Логин: `https://<project>.vercel.app/admin/login`
- Контент-редактор: `https://<project>.vercel.app/admin/content`

Там можно менять тексты, фото, кнопки, ссылки, канал проверки и шаги воронки.