from rest_framework import serializers
from .models import Source, Article, ReadingSession
from django.contrib.auth import get_user_model

User = get_user_model()
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'daily_reading_limit']

class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ['id', 'name', 'url', 'rss_url', 'category']

class ArticleSerializer(serializers.ModelSerializer):
    source_name = serializers.ReadOnlyField(source='source.name')

    class Meta:
        model = Article

        fields = ['id', 'source_name', 'category', 'title', 'content', 'url', 'published_at']

class HeartbeatSerializer(serializers.Serializer):
    """
    Специальный сериализатор для валидации входящих пингов от фронтенда
    """
    duration_seconds = serializers.IntegerField(min_value=1, max_value=60)