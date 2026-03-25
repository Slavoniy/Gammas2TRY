# Gamma Presentations Backend

FastAPI бэкенд для генерации презентаций через Gamma API. Принимает вебхуки от Tilda после оплаты, генерирует презентацию и отправляет ссылку на email клиента.

## Запуск локально

```
pip install -r requirements.txt
cp .env.example .env  # заполнить переменные
uvicorn main:app --reload
```

## Переменные окружения (.env)

| Переменная | Описание |
|---|---|
| `GAMMA_API_KEY` | ключ Gamma API |
| `ALLOWED_ORIGINS` | домены через запятую, например: `https://presentaciya.ru` |
| `SMTP_HOST` | `smtp.timeweb.ru` |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | `noreply@presentaciya.ru` |
| `SMTP_PASSWORD` | пароль SMTP |
| `SMTP_FROM` | `noreply@presentaciya.ru` |
| `TILDA_SECRET` | секретный токен для защиты webhook (опционально) |
| `MOCK_MODE` | `false` |

## API эндпоинты

```
POST /webhook/tilda     — приём заказов от Tilda
GET  /api/health        — проверка работоспособности
POST /api/generate      — прямая генерация (для тестов)
GET  /api/generation/id — статус генерации
GET  /api/themes        — список тем Gamma
```
