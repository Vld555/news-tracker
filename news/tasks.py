import logging
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from celery import shared_task
from sentence_transformers import SentenceTransformer
from .models import Article, Source

logger = logging.getLogger(__name__)

embedder = None
MODEL_NAME = 'DeepPavlov/rubert-base-cased-sentence'

@shared_task
def parse_rss_and_embed():
    global embedder

    if embedder is None:
        logger.info(f"Загрузка ML-модели: {MODEL_NAME}...")
        embedder = SentenceTransformer(MODEL_NAME)
    sources = Source.objects.exclude(rss_url__isnull=True).exclude(rss_url__exact='') # скачиваем новотси
    
    for source in sources:
        logger.info(f"Парсинг источника: {source.name}")
        try:
            response = requests.get(sources.rss_url, timeout=50)
            soup = BeautifulSoup(response.content, '')
            items = soup.find_all('item')

            for item in items[:10]:
                title = item.title.text if item.title else 'Без заголовка'
                link = item.link.text if item.link else ''
                description = item.description.text if item.description else ''
                
                # Если статья с таким URL уже есть в базе — пропускаем
                if not link or Article.objects.filter(url=link).exists():
                    continue
                    
                # 1. Готовим текст для нейросети
                text_for_embedding = f"{title}. {description}"
                
                # 2. Магия ML: превращаем текст в вектор [0.12, -0.45, ...]
                # tolist() нужен, т.к. pgvector ожидает обычный python-список, а не numpy array
                embedding = embedder.encode(text_for_embedding).tolist()
                
                # 3. Сохраняем в PostgreSQL
                Article.objects.create(
                    source=source,
                    title=title,
                    content=description,
                    url=link,
                    published_at=timezone.now(), # Для упрощения берем текущее время
                    embedding=embedding
                )
                logger.info(f"✅ Успешно добавлена и векторизована статья: {title}")

        except Exception as e:
            logger.error(f"❌ Ошибка при парсинге {source.name}: {e}")
