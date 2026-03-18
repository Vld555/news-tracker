from django.db import models
from django.contrib.auth.models import AbstractUser
from pgvector.django import VectorField
from django.utils import timezone

class User(AbstractUser):
    daily_reading_limit = models.IntegerField(
        default=3600, help_text="Лимит чтения в секундах")


class Source(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    rss_url = models.URLField(blank=True, null=True)
    category = models.CharField(
        max_length=100, help_text="Основная тематика источника")

    def __str__(self):
        return self.name


class Article(models.Model):
    source = models.ForeignKey(
        Source, on_delete=models.CASCADE, related_name='articles')
    title = models.CharField(max_length=500)
    content = models.TextField()
    url = models.URLField(unique=True)
    published_at = models.DateTimeField()

    # Вектор для RAG (размерность 768 под популярные энкодеры)
    embedding = VectorField(dimensions=768, blank=True, null=True)

    def __str__(self):
        return self.title


class ReadingSession(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reading_sessions')
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    start_time = models.DateTimeField(default=timezone.now)
    duration_seconds = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.article.title[:20]} ({self.duration_seconds}s)"
