# KLEIN Bot

Телеграм-бот с панелью воркера и администратора. Управление реф-ссылками, доменами и лендингами.

## Стек

- Python 3.11+
- aiogram 3.x
- PostgreSQL + SQLAlchemy (async) + asyncpg
- pydantic-settings

## Установка

```bash
# 1. Клонируем / переходим в папку
cd klaz-bot

# 2. Создаём виртуальное окружение
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# 3. Устанавливаем зависимости
pip install -r requirements.txt

# 4. Настраиваем .env
cp .env.example .env
# Заполняем BOT_TOKEN, ADMIN_IDS, DB_*, SERVER_IP
```

## Конфигурация (.env)

| Переменная   | Описание                                      |
|--------------|-----------------------------------------------|
| BOT_TOKEN    | Токен бота от @BotFather                      |
| ADMIN_IDS    | TG ID администраторов через запятую: 123,456  |
| DB_HOST      | Хост PostgreSQL (default: localhost)          |
| DB_PORT      | Порт PostgreSQL (default: 5432)               |
| DB_NAME      | Имя базы данных                               |
| DB_USER      | Пользователь БД                               |
| DB_PASS      | Пароль БД                                     |
| SERVER_IP    | IP сервера для привязки доменов               |
| BASE_URL     | Базовый URL для реф-ссылок                    |

## Запуск

```bash
python main.py
```

## Структура

```
klaz-bot/
├── bot/
│   ├── handlers/
│   │   ├── common.py     # /start, меню
│   │   ├── worker.py     # панель воркера
│   │   └── admin.py      # панель админа
│   ├── keyboards/
│   │   └── inline.py     # все клавиатуры
│   ├── middlewares/
│   │   └── auth.py       # авторизация, создание юзера
│   └── utils/
│       └── link_generator.py  # генерация slug
├── db/
│   ├── models.py          # SQLAlchemy модели
│   └── database.py        # engine, session
├── config.py              # настройки через .env
├── main.py                # точка входа
└── requirements.txt
```

## Роли

- **Воркер** — создаёт реф-ссылки, добавляет домены, смотрит статистику
- **Админ** — управляет воркерами, добавляет лендинги, видит всю статистику

## Привязка домена к IP

1. Воркер добавляет домен в боте
2. Прописывает A-запись на `SERVER_IP`
3. Нажимает «Проверить DNS» — бот делает резолв через `socket.gethostbyname`
4. После подтверждения домен становится активным и используется в реф-ссылках

## Трекинг (будущий этап)

Для записи кликов и лидов нужен отдельный веб-сервер (FastAPI/aiohttp), который:
- Принимает GET `/ref/{slug}` → записывает Stat(event="click") → редиректит на лендинг
- Принимает POST `/lead/{slug}` → записывает Stat(event="lead") → уведомляет воркера в бот
