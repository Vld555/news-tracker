# News Tracker

Система для отслеживания и рекомендации новостей. Проект включает в себя веб-интерфейс на Django, систему фоновых задач Celery, машинное обучение на базе CatBoost и векторную базу данных PostgreSQL (pgvector).

## Стек технологий

*   **Backend:** Python 3.11, Django, Django REST Framework
*   **Database:** PostgreSQL 16 с расширением pgvector для векторного поиска
*   **Message Broker & Cache:** Redis 7
*   **Background Tasks:** Celery
*   **Machine Learning:** CatBoost
*   **Containerization:** Docker & Docker Compose

## Структура проекта

*   `core/` — Основные настройки Django (settings, urls, celery app).
*   `news/` — Приложение Django:
    *   `models.py` — Модели данных (статьи, сессии чтения и др.).
    *   `views.py`, `urls.py` — Логика отображения и маршрутизация.
    *   `tasks.py` — Асинхронные задачи Celery.
    *   `ml.py` — Интеграция с ML моделью CatBoost.
*   `html/` — Шаблоны для отображения страниц (index, dashboard, article и т.д.).
*   `ml_models/` — Сохраненные веса обученных моделей CatBoost.
*   `docker-compose.yml` & `Dockerfile` — Конфигурация для запуска в Docker.

## Запуск проекта

Проект полностью контейнеризирован. Для его запуска вам потребуется установленный Docker и Docker Compose.

1.  **Клонируйте репозиторий**.
2.  **Запустите контейнеры:**
    Находясь в корне проекта (где расположен `docker-compose.yml`), выполните команду:
    ```bash
    docker compose up -d
    ```
    Это запустит следующие сервисы:
    *   `db` (PostgreSQL + pgvector)
    *   `redis`
    *   `web` (Django сервер на порту 8000)
    *   `celery` (Celery worker)
    *   `celery-beat` (Celery beat для периодических задач, если настроено)

3.  **Применение миграций:**
    После того как база данных будет готова, выполните миграции Django:
    ```bash
    docker compose exec web python manage.py migrate
    ```

4.  **Создание суперпользователя** (опционально, для доступа в админку):
    ```bash
    docker compose exec web python manage.py createsuperuser
    ```

5.  **Доступ к приложению:**
    *   Веб-интерфейс: [http://localhost:8000](http://localhost:8000)
    *   Панель администратора: [http://localhost:8000/admin](http://localhost:8000/admin)

## Остановка проекта

Чтобы остановить контейнеры, выполните:
```bash
docker compose down
```

Если вы хотите также удалить данные (включая volume базы данных), используйте флаг `-v`:
```bash
docker compose down -v
```