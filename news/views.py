import os
from catboost import CatBoostClassifier
import pandas as pd
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated, AllowAny

from .models import Source, Article, ReadingSession, User
from .serializers import SourceSerializer, ArticleSerializer, HeartbeatSerializer, UserSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import now
from django.db.models import Sum
from datetime import timedelta
from .models import ReadingSession, Source
from .serializers import UserRegistrationSerializer
from rest_framework.pagination import PageNumberPagination

class ArticlePagination(PageNumberPagination):
    page_size = 10 # По 10 статей на страницу
    page_size_query_param = 'page_size'


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def patch(self, request, *args, **kwargs):

        if 'daily_reading_limit' in request.data:
            try:
                request.data['daily_reading_limit'] = int(request.data['daily_reading_limit'])
            except ValueError:
                pass
        return super().patch(request, *args, **kwargs)

class SourceViewSet(viewsets.ModelViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
class SourceListCreateView(generics.ListCreateAPIView):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [IsAuthenticated]



class ArticleListView(generics.ListAPIView):
    serializer_class = ArticleSerializer
    # permission_classes = [IsAuthenticated] # Раскомментируй, если лента только для залогиненных
    pagination_class = ArticlePagination

    def get_queryset(self):
        user = self.request.user
        
        # 1. Берем 100 самых свежих статей из базы (Холодный старт)
        queryset = Article.objects.order_by('-published_at')[:100]
        
        # Если юзер не авторизован, отдаем просто свежие новости по дате
        if not user.is_authenticated:
            return queryset

        model_path = f'ml_models/catboost_user_{user.id}.cbm'
        
        # 2. Если модель еще не обучилась (нет файла), отдаем ленту по дате
        if not os.path.exists(model_path):
            return queryset

        # 3. УМНОЕ РАНЖИРОВАНИЕ (Inference)
        try:
            # Загружаем твою персональную модель
            model = CatBoostClassifier()
            model.load_model(model_path)

            data = []
            articles_list = list(queryset) # Выгружаем 100 статей в список
            
            # Собираем признаки точно так же, как при обучении
            for article in articles_list:
                row = {
                    'category': article.category or 'Общее',
                    'source': article.source.name,
                }
                if article.embedding is not None:
                    for i, val in enumerate(article.embedding):
                        row[f'emb_{i}'] = val
                else:
                    for i in range(768):
                        row[f'emb_{i}'] = 0.0
                data.append(row)

            # Создаем DataFrame (таблицу) для CatBoost
            df = pd.DataFrame(data)
            
            # Получаем вероятности (от 0.0 до 1.0), что статья тебе зайдет
            # [:, 1] означает "взять вероятность для класса 1 (Позитив)"
            probabilities = model.predict_proba(df)[:, 1]

            # Привязываем предсказанные вероятности к объектам статей
            for i, article in enumerate(articles_list):
                article.match_score = probabilities[i]

            # Сортируем: чем выше вероятность (score), тем выше статья в ленте!
            articles_list.sort(key=lambda x: x.match_score, reverse=True)
            
            return articles_list

        except Exception as e:
            print(f"Ошибка при ранжировании: {e}")
            # Если что-то пошло не так (например, ошибка Pandas), отдаем просто по дате
            return queryset


class AnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = now().date()
        week_ago = today - timedelta(days=7)

        # 1. Берем сессии пользователя за последние 7 дней (ИСПОЛЬЗУЕМ start_time)
        sessions = ReadingSession.objects.filter(
            user=user, 
            start_time__date__gte=week_ago
        )

        # 2. Считаем время чтения за сегодня (в минутах)
        today_sessions = sessions.filter(start_time__date=today)
        today_sec = today_sessions.aggregate(total=Sum('duration_seconds'))['total'] or 0
        today_min = today_sec // 60

        # 3. Данные для круговой диаграммы (группировка по НОВОЙ категории статьи)
        categories_qs = sessions.values('article__category').annotate(
            total_time=Sum('duration_seconds')
        ).order_by('-total_time')

        # Используем поле 'article__category' вместо 'article__source__category'
        cat_labels = [item['article__category'] or 'Без категории' for item in categories_qs]
        cat_data = [item['total_time'] // 60 for item in categories_qs]

        # 4. Данные для столбчатой диаграммы (активность по дням)
        days_labels = []
        days_data = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            # Ищем сумму секунд для конкретного дня (ИСПОЛЬЗУЕМ start_time)
            day_sec = sessions.filter(start_time__date=d).aggregate(total=Sum('duration_seconds'))['total'] or 0
            
            days_labels.append(d.strftime('%d.%m'))
            days_data.append(day_sec // 60)

        return Response({
            "today_minutes": today_min,
            "limit_minutes": (getattr(user, 'daily_reading_limit', 3600) or 0) // 60,
            "categories": {"labels": cat_labels, "data": cat_data},
            "activity": {"labels": days_labels, "data": days_data}
        })
    

class ArticleDetailView(generics.RetrieveAPIView):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    permission_classes = [] # Для теста разрешим всем



from django.utils.timezone import now
from datetime import timedelta

class HeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # Получаем количество секунд из запроса (по умолчанию 15)
        seconds_to_add = request.data.get('duration_seconds', 15)
        
        try:
            article = Article.objects.get(pk=pk)
            
            # Ищем или создаем активную сессию (start_time из твоих моделей)
            session, created = ReadingSession.objects.get_or_create(
                user=request.user,
                article=article,
                is_active=True,
                # Если сессия создана менее 2 часов назад, продолжаем её
                start_time__gte=now() - timedelta(hours=2),
                defaults={'duration_seconds': 0}
            )
            
            # Прибавляем полученные секунды
            session.duration_seconds += int(seconds_to_add)
            session.save()
            
            return Response({
                "status": "success",
                "total_seconds": session.duration_seconds
            })
            
        except Article.DoesNotExist:
            return Response({"error": "Статья не найдена"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
        
class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny] # Разрешаем доступ всем (даже без токена)
    serializer_class = UserRegistrationSerializer