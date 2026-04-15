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
    Собирает историю чтения пользователя и обучает персональную модель CatBoost
    с учетом взвешивания явного и неявного фидбека.
    """
    # 1. Загружаем все сессии чтения пользователя
    sessions = ReadingSession.objects.filter(user_id=user_id)

    if not sessions.exists():
        logger.warning(f"У юзера {user_id} нет истории сессий для обучения.")
        return False

    data = []
    seen_article_ids = []

    # Функция для извлечения фичей из статьи
    def extract_features(article):
        row = {
            'article_id': article.id,
            'category': article.category or 'Общее',
            'source': article.source.name,
        }
        if article.embedding is not None:
            for i, val in enumerate(article.embedding):
                row[f'emb_{i}'] = val
        else:
            for i in range(768):
                row[f'emb_{i}'] = 0.0
        return row

    # 2. ОБРАБАТЫВАЕМ СЕССИИ (Явный и Неявный фидбек)
    for session in sessions:
        article = session.article
        seen_article_ids.append(article.id)
        
        row = extract_features(article)
        
        # ЛОГИКА ВЗВЕШИВАНИЯ
        if session.explicit_feedback == 1:
            row['label'] = 1
            row['weight'] = 5.0  # Лайк: мощный позитивный сигнал
        elif session.explicit_feedback == -1:
            row['label'] = 0
            row['weight'] = 5.0  # Дизлайк: мощный негативный сигнал
        else:
            # Неявный фидбек (опираемся на таймер)
            if session.duration_seconds >= 15:
                row['label'] = 1
                row['weight'] = 1.0  # Долго читал: обычный позитивный сигнал
            else:
                row['label'] = 0
                row['weight'] = 1.0  # Открыл и сразу закрыл: обычный негативный сигнал
                
        data.append(row)

    # 3. ДОБАВЛЯЕМ НЕПРОЧИТАННЫЕ СТАТЬИ (Фоновый негатив)
    # Это нужно, чтобы модель не забывала о статьях, которые юзер просто проигнорировал в ленте
    week_ago = now() - timedelta(days=7)
    negatives = Article.objects.filter(published_at__gte=week_ago)\
                               .exclude(id__in=seen_article_ids)\
                               .order_by('?')[:len(seen_article_ids) * 2] # Берем в 2 раза больше непрочитанных

    for n in negatives:
        row = extract_features(n)
        row['label'] = 0
        row['weight'] = 0.5  # Игнор в ленте — слабый негативный сигнал
        data.append(row)

    # 4. ФОРМИРУЕМ DATAFRAME
    df = pd.DataFrame(data)
    os.makedirs('ml_models', exist_ok=True)
    csv_path = f'ml_models/dataset_user_{user_id}.csv'
    df.to_csv(csv_path, index=False)
    
    X = df.drop(columns=['article_id', 'label', 'weight'])
    y = df['label']
    weights = df['weight']  # Выделяем колонку с весами

    cat_features = ['category', 'source']

    # 5. ОБУЧАЕМ CATBOOST
    model = CatBoostClassifier(
        iterations=100,
        learning_rate=0.1,
        depth=6,
        cat_features=cat_features,
        verbose=False
    )
    
    logger.info(f"Начинаю обучение модели для юзера {user_id} на {len(df)} примерах...")
    
    # ПЕРЕДАЕМ ВЕСА В МОДЕЛЬ (sample_weight)
    model.fit(X, y, sample_weight=weights)

    # 6. СОХРАНЯЕМ МОДЕЛЬ
    os.makedirs('ml_models', exist_ok=True)
    model_path = f'ml_models/catboost_user_{user_id}.cbm'
    model.save_model(model_path)
    logger.info(f"✅ Модель сохранена: {model_path}")
    
    return True