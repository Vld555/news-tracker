from django.contrib import admin
from .models import User, Source, Article, ReadingSession


admin.site.register(User)
admin.site.register(Source)
admin.site.register(ReadingSession)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'published_at')
    list_filter = ('source',)
    search_fields = ('title', 'content')