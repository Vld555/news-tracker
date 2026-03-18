import os
import pandas as pd
from catboost import CatBoostClassifier
from django.utils.timezone import now
from datetime import timedelta
from .models import Article, ReadingSession, User
import logging

logger = logging.getLogger(__name__)

def train_user_model(user_id):
    """
    Собирает историю чтения пользователя и обучает персональную модель CatBoost.
    """
    # 1. СОБИРАЕМ ПОЗИТИВЫ (Статьи, которые юзер читал дольше 15 секунд)
    sessions = ReadingSession.objects.filter(
        user_id=user_id, 
        duration_seconds__gte=15
    )
    positive_article_ids = list(sessions.values_list('article_id', flat=True))

    if len(positive_article_ids) < 5:
        logger.warning(f"У юзера {user_id} мало прочитанных статей для обучения (< 5).")
        return False

    positives = Article.objects.filter(id__in=positive_article_ids)

    # 2. СОБИРАЕМ НЕГАТИВЫ (Статьи за последнюю неделю, которые юзер НЕ открывал)
    week_ago = now() - timedelta(days=7)
    negatives = Article.objects.filter(published_at__gte=week_ago)\
                               .exclude(id__in=positive_article_ids)\
                               .order_by('?')[:len(positives) * 3] # Берем в 3 раза больше негативов

    data = []
    
    # Функция для извлечения фичей (признаков) из статьи
    def extract_features(article, label):
        row = {
            'article_id': article.id,
            'category': article.category or 'Общее',
            'source': article.source.name,
            'label': label
        }
        # Распаковываем наш вектор из 768 чисел в отдельные колонки
        if article.embedding is not None:
            for i, val in enumerate(article.embedding):
                row[f'emb_{i}'] = val
        else:
            for i in range(768):
                row[f'emb_{i}'] = 0.0
        return row

    # 3. ФОРМИРУЕМ ДАТАСЕТ (Pandas DataFrame)
    for p in positives:
        data.append(extract_features(p, 1))
    for n in negatives:
        data.append(extract_features(n, 0))

    df = pd.DataFrame(data)

    # 4. ПОДГОТОВКА К ОБУЧЕНИЮ
    X = df.drop(columns=['article_id', 'label'])
    y = df['label']

    # Указываем CatBoost, какие колонки являются текстом/категориями, а какие - числами (векторами)
    cat_features = ['category', 'source']

    # 5. ОБУЧАЕМ CATBOOST
    model = CatBoostClassifier(
        iterations=100,         # Количество деревьев
        learning_rate=0.1,
        depth=6,
        cat_features=cat_features,
        verbose=False           # Не спамить в консоль
    )
    
    logger.info(f"Начинаю обучение модели для юзера {user_id} на {len(df)} примерах...")
    model.fit(X, y)

    # 6. СОХРАНЯЕМ ВЕСА МОДЕЛИ
    os.makedirs('ml_models', exist_ok=True)
    model_path = f'ml_models/catboost_user_{user_id}.cbm'
    model.save_model(model_path)
    logger.info(f"✅ Модель сохранена: {model_path}")
    
    return True