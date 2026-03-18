import logging
import requests
import nltk # Добавили импорт для загрузки словарей
from bs4 import BeautifulSoup
from django.utils import timezone
from celery import shared_task
from sentence_transformers import SentenceTransformer
from .models import Article, Source, User
from newspaper import Article as NewspaperArticle
from datetime import timedelta
from .ml import train_user_model

logger = logging.getLogger(__name__)

# Загружаем нужные компоненты для NLP один раз при импорте
try:
    nltk.download('punkt', quiet=True)
except:
    pass

embedder = None
MODEL_NAME = 'DeepPavlov/rubert-base-cased-sentence'

@shared_task
def parse_rss_and_embed():
    global embedder
    if embedder is None:
        embedder = SentenceTransformer(MODEL_NAME)
    
    sources = Source.objects.exclude(rss_url__isnull=True).exclude(rss_url__exact='')
    
    for source in sources:
        try:
            response = requests.get(source.rss_url, timeout=30)
            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')

            for item in items[:10]:
                link = item.link.text if item.link else ''
                if not link or Article.objects.filter(url=link).exists():
                    continue
                
                full_content = ""
                article_category = None
                
                # Попытка 1: Качаем полный текст через newspaper3k
                try:
                    news_article = NewspaperArticle(link, language='ru') 
                    news_article.download()
                    news_article.parse()
                    full_content = news_article.text # СОХРАНЯЕМ ТЕКСТ СРАЗУ
                    
                    # Пытаемся сделать NLP отдельно, чтобы не сломать всё
                    try:
                        news_article.nlp()
                        if news_article.keywords:
                            article_category = news_article.keywords[0].capitalize()
                    except:
                        pass
                except Exception as e:
                    logger.warning(f"Newspaper3k не справился с {link}: {e}")

                # Попытка 2 (Золотое правило): Если текст не скачался, берем из RSS
                if not full_content or len(full_content) < 150:
                    rss_description = item.description.text if item.description else ""
                    full_content = BeautifulSoup(rss_description, "html.parser").get_text()

                # Попытка 3: Ищем категорию в RSS, если NLP не сработал
                if not article_category:
                    article_category = item.category.text if item.category else None
                
                # Финальный запасной вариант для категории
                if not article_category:
                    article_category = source.category or "Общее"

                if not full_content:
                    full_content = "Текст статьи временно недоступен."

                title = item.title.text if item.title else 'Без заголовка'
                
                # Делаем эмбеддинг
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
                logger.info(f"✅ Добавлена статья [{article_category}]: {title}")

        except Exception as e:
            logger.error(f"❌ Ошибка источника {source.name}: {e}")

@shared_task
def clear_old_articles():
    # Удаляем статьи старше 24 часов (можешь поменять на 2 часа для теста)
    threshold = timezone.now() - timedelta(hours=24)
    deleted, _ = Article.objects.filter(published_at__lt=threshold).delete()
    logger.info(f"🧹 Очистка: удалено {deleted} старых статей.")



@shared_task
def retrain_recommendation_models():
    """Задача запускается по расписанию и обновляет ML-модели всех активных юзеров"""
    users = User.objects.all()
    updated_count = 0
    
    for user in users:
        logger.info(f"Запуск обучения для юзера {user.username}...")
        success = train_user_model(user.id)
        if success:
            updated_count += 1
            
    logger.info(f"🎯 Обучение завершено. Обновлено моделей: {updated_count}")
    return updated_count