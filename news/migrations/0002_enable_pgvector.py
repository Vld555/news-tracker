# filepath: /news/migrations/0002_enable_pgvector.py
# ...existing code...
from django.db import migrations
from pgvector.django import VectorExtension # <-- Добавьте импорт

class Migration(migrations.Migration):

    dependencies = [
        ('news', '0001_initial'), # Здесь ссылка на первую миграцию
    ]

    operations = [
        VectorExtension() 
    ]