from rest_framework import serializers
from .models import Source, Article, ReadingSession

class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = '__all__'

class ArticleSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)

    class Meta:
        model = Article
        fields = ['id', 'source', 'source_name', 'title', 'content', 'url', 'published_at']
        # Поле embedding мы умышленно исключаем

class HeartbeatSerializer(serializers.Serializer):
    """
    Специальный сериализатор для валидации входящих пингов от фронтенда
    """
    duration_seconds = serializers.IntegerField(min_value=1, max_value=60)