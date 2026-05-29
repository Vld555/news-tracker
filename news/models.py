from django.db import models
from django.contrib.auth.models import AbstractUser
from pgvector.django import VectorField
from django.utils import timezone

class User(AbstractUser):
    daily_reading_limit = models.IntegerField(
        default=3600, help_text="Лимит чтения в секундах")

class UserInterest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interests')
    category = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'category')

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
    category = models.CharField(max_length=100, blank=True, null=True) 
    url = models.URLField(unique=True)
    published_at = models.DateTimeField()
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

    explicit_feedback = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.article.title[:20]} ({self.duration_seconds}s)"

class UserDashboardAnalysis(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dashboard_analysis')
    summary = models.TextField(default="Анализ рациона подготавливается...")
    suggestions = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Analysis for {self.user.username}"