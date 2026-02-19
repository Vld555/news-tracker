from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated

from .models import Source, Article, ReadingSession
from .serializers import SourceSerializer, ArticleSerializer, HeartbeatSerializer


class SourceViewSet(viewsets.ModelViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


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
