from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SourceViewSet, ArticleViewSet, AnalyticsAPIView

router = DefaultRouter()
router.register(r'sources', SourceViewSet)
router.register(r'articles', ArticleViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('analytics/', AnalyticsAPIView.as_view(), name='analytics'),
]