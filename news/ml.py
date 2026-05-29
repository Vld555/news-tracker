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
    sessions = ReadingSession.objects.filter(user_id=user_id)

    if not sessions.exists():
        logger.warning(f"У юзера {user_id} нет истории сессий для обучения.")
        return False

    data = []
    seen_article_ids = []

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

    for session in sessions:
        article = session.article
        seen_article_ids.append(article.id)
        row = extract_features(article)
        if session.explicit_feedback == 1:
            row['label'] = 1
            row['weight'] = 5.0  
        elif session.explicit_feedback == -1:
            row['label'] = 0
            row['weight'] = 5.0  
        else:
            if session.duration_seconds >= 15:
                row['label'] = 1
                row['weight'] = 1.0  
            else:
                row['label'] = 0
                row['weight'] = 1.0    
        data.append(row)

    week_ago = now() - timedelta(days=7)
    negatives = Article.objects.filter(published_at__gte=week_ago)\
                               .exclude(id__in=seen_article_ids)\
                               .order_by('?')[:len(seen_article_ids) * 2] 

    for n in negatives:
        row = extract_features(n)
        row['label'] = 0
        row['weight'] = 0.5  
        data.append(row)

    df = pd.DataFrame(data)
    os.makedirs('ml_models', exist_ok=True)
    csv_path = f'ml_models/dataset_user_{user_id}.csv'
    df.to_csv(csv_path, index=False)
    
    X = df.drop(columns=['article_id', 'label', 'weight'])
    y = df['label']
    weights = df['weight']  

    cat_features = ['category', 'source']

    model = CatBoostClassifier(
        iterations=100,
        learning_rate=0.1,
        depth=6,
        cat_features=cat_features,
        verbose=False
    )
    
    logger.info(f"Начинаю обучение модели для юзера {user_id} на {len(df)} примерах...")

    model.fit(X, y, sample_weight=weights)

    os.makedirs('ml_models', exist_ok=True)
    model_path = f'ml_models/catboost_user_{user_id}.cbm'
    model.save_model(model_path)
    logger.info(f"✅ Модель сохранена: {model_path}")
    
    return True