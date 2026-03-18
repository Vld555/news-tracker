from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SourceViewSet, ArticleViewSet, AnalyticsAPIView, ArticleDetailView, HeartbeatView, SourceListCreateView

router = DefaultRouter()
router.register(r'sources', SourceViewSet)
router.register(r'articles', ArticleViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('analytics/', AnalyticsAPIView.as_view(), name='analytics'),
    path('articles/<int:pk>/', ArticleDetailView.as_view(), name='article-detail'),
    path('articles/<int:pk>/heartbeat/', HeartbeatView.as_view(), name='article-heartbeat'),
    path('sources/', SourceListCreateView.as_view(), name='source-list-create')
]