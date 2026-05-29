import logging
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from celery import shared_task
from sentence_transformers import SentenceTransformer
from .models import Article, Source, User, UserDashboardAnalysis, ReadingSession
from newspaper import Article as NewspaperArticle, Config # ДОБАВИЛИ Config
from datetime import timedelta
from .ml import train_user_model

logger = logging.getLogger(__name__)

embedder = None
MODEL_NAME = 'DeepPavlov/rubert-base-cased-sentence'

# news/tasks.py
import requests
import json
from .models import User, ReadingSession, UserDashboardAnalysis
from django.db.models import Sum
from django.utils.timezone import now
from datetime import timedelta

@shared_task
def update_llm_dashboard_analysis():
    users = User.objects.all()
    ollama_url = "http://host.docker.internal:11434/api/generate"

    for user in users:
        today = now().date()
        week_ago = today - timedelta(days=7)
        sessions = ReadingSession.objects.filter(user=user, start_time__date__gte=week_ago)
        
        categories_stats = sessions.values('article__category').annotate(
            total_time=Sum('duration_seconds')
        ).order_by('-total_time')[:3]

        cat_list = [c['article__category'] or "Общее" for c in categories_stats]
        top_cat = cat_list[0] if cat_list else "Разное"

        # ЖЕСТКИЙ ПРОМПТ В ФОРМАТЕ ДИАЛОГА
        prompt = f"""System: Выдать только валидный JSON. Никакого текста, никаких пояснений.
            User: Категории пользователя: {cat_list}.
            Assistant:
            {{
            "summary": "На этой неделе вас больше всего интересовала тема {top_cat}.",
            "suggestions": ["Технологии", "Наука", "Культура"]
            }}
            User: Категории пользователя: {cat_list}. Сгенерируй новые темы.
            Assistant:
        """

        try:
            response = requests.post(ollama_url, json={
                "model": "qwen2.5:0.5b",
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0.0 
                }
            }, timeout=60)
            
            raw_text = response.json().get('response', '').strip()
            
            start_idx = raw_text.find('{')
            end_idx = raw_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                clean_json = raw_text[start_idx:end_idx+1]
                result = json.loads(clean_json)
            else:
                raise ValueError("В ответе не найдено JSON структуры.")
            
            UserDashboardAnalysis.objects.update_or_create(
                user=user,
                defaults={
                    'summary': result.get('summary', f'Мы видим, что вы активно читаете статьи в категории "{top_cat}".'),
                    'suggestions': result.get('suggestions', [])
                }
            )
            print(f"✅ Успешный анализ для {user.username}")
            
        except Exception as e:
            print(f"❌ Ошибка LLM для {user.username}: {e}. Используем fallback.")
            # Если LLM снова выдала бред, ставим красивую дефолтную заглушку вместо ошибки
            UserDashboardAnalysis.objects.update_or_create(
                user=user,
                defaults={
                    'summary': f'Ваш основной фокус на этой неделе: "{top_cat}". Продолжайте в том же духе!',
                    'suggestions': ['IT', 'Инновации', 'Искусство']
                }
            )
        
@shared_task
def parse_rss_and_embed():
    global embedder
    logger.info("🚀 Запуск задачи parse_rss_and_embed...")
    
    if embedder is None:
        logger.info("⏳ Загрузка модели SentenceTransformer (может занять 1-2 минуты при первом запуске)...")
        embedder = SentenceTransformer(MODEL_NAME)
        logger.info("✅ Модель NLP успешно загружена!")
    
    sources = Source.objects.exclude(rss_url__isnull=True).exclude(rss_url__exact='')
    logger.info(f"📡 Найдено источников для парсинга: {sources.count()}")
    
    for source in sources:
        logger.info(f"🔄 Парсинг источника: {source.name} ({source.rss_url})")
        try:
            # 1. Загружаем RSS с таймаутом
            response = requests.get(source.rss_url, timeout=15)
            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')
            logger.info(f"   Найдено {len(items)} записей в ленте.")

            for item in items[:10]:
                link = item.link.text if item.link else ''
                if not link:
                    continue
                
                if Article.objects.filter(url=link).exists():
                    continue # Пропускаем уже существующие статьи
                
                full_content = ""
                
                # 2. Настраиваем Newspaper3k с жесткими лимитами
                config = Config()
                config.request_timeout = 10
                config.language = 'ru'
                config.fetch_images = False # Не тратим время на картинки
                
                try:
                    news_article = NewspaperArticle(link, config=config) 
                    news_article.download()
                    news_article.parse()
                    full_content = news_article.text
                    # Мы полностью удалили .nlp(), так как именно он вешал Celery!
                except Exception as e:
                    logger.warning(f"   ⚠️ Не удалось скачать текст с {link}: {e}")

                if not full_content or len(full_content) < 150:
                    rss_description = item.description.text if item.description else ""
                    full_content = BeautifulSoup(rss_description, "html.parser").get_text()

                # 4. Категорию берем из RSS или ставим дефолтную (убрали NLP)
                article_category = item.category.text if item.category else source.category or "Общее"

                if not full_content or len(full_content) < 20:
                    full_content = "Текст статьи недоступен. Читайте подробности по ссылке."

                title = item.title.text if item.title else 'Без заголовка'
                
                embedding = embedder.encode(f"{title}. {full_content[:500]}").tolist()
                
                Article.objects.create(
                    source=source,
                    title=title,
                    content=full_content,
                    category=article_category,
                    url=link,
                    published_at=timezone.now(),
                    embedding=embedding
                )
                logger.info(f"   ✅ Добавлена статья: {title}")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки источника {source.name}: {e}")

@shared_task
def clear_old_articles():
    threshold = timezone.now() - timedelta(hours=24)
    deleted, _ = Article.objects.filter(published_at__lt=threshold).delete()
    logger.info(f"🧹 Очистка: удалено {deleted} старых статей.")

@shared_task
def retrain_recommendation_models():
    users = User.objects.all()
    updated_count = 0
    for user in users:
        logger.info(f"Запуск обучения для юзера {user.username}...")
        success = train_user_model(user.id)
        if success:
            updated_count += 1
    logger.info(f"🎯 Обучение завершено. Обновлено моделей: {updated_count}")
    return updated_count