from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated

from .models import Source, Article, ReadingSession
from .serializers import SourceSerializer, ArticleSerializer, HeartbeatSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import now
from django.db.models import Sum
from datetime import timedelta
from .models import ReadingSession, Source



class SourceViewSet(viewsets.ModelViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
class SourceListCreateView(generics.ListCreateAPIView):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # При желании можно привязать источник к пользователю, 
        # если добавишь ForeignKey в модель Source
        serializer.save()

class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Пока используем ReadOnly, так как статьи будут добавляться 
    автоматически через Celery-воркеры (парсинг).
    """
    queryset = Article.objects.all().order_by('-published_at')
    serializer_class = ArticleSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def heartbeat(self, request, pk=None):
        article = self.get_object()
        serializer = HeartbeatSerializer(data=request.data)

        if serializer.is_valid():
            duration = serializer.validated_data['duration_seconds']

            # Ищем активную сессию чтения или создаем новую
            session, created = ReadingSession.objects.get_or_create(
                user=request.user,
                article=article,
                is_active=True,
                defaults={'duration_seconds': 0}
            )

            # Прибавляем полученные секунды
            session.duration_seconds += duration
            session.save()

            return Response({
                'status': 'success',
                'session_id': session.id,
                'total_duration': session.duration_seconds
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
            "limit_minutes": getattr(user, 'daily_reading_limit', 60), 
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