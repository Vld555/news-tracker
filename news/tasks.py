import logging
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from celery import shared_task
from sentence_transformers import SentenceTransformer
from .models import Article, Source, User
from newspaper import Article as NewspaperArticle, Config # ДОБАВИЛИ Config
from datetime import timedelta
from .ml import train_user_model

logger = logging.getLogger(__name__)

embedder = None
MODEL_NAME = 'DeepPavlov/rubert-base-cased-sentence'

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

                # 3. Запасной вариант: берем из RSS, если скачалось слишком мало текста
                if not full_content or len(full_content) < 150:
                    rss_description = item.description.text if item.description else ""
                    full_content = BeautifulSoup(rss_description, "html.parser").get_text()

                # 4. Категорию берем из RSS или ставим дефолтную (убрали NLP)
                article_category = item.category.text if item.category else source.category or "Общее"

                if not full_content or len(full_content) < 20:
                    full_content = "Текст статьи недоступен. Читайте подробности по ссылке."

                title = item.title.text if item.title else 'Без заголовка'
                
                # 5. Делаем эмбеддинг
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