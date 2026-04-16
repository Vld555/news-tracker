from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import \
    SourceViewSet, ArticleListView, AnalyticsAPIView, ArticleDetailView, HeartbeatView, UserProfileView, UserRegistrationView, ArticleRateView, AddInterestView

# Роутер автоматически создаст эндпоинты для GET, POST, PUT и DELETE запросов к источникам
router = DefaultRouter()
router.register(r'sources', SourceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('articles/<int:pk>/rate/', ArticleRateView.as_view(), name='article-rate'),
    path('articles/', ArticleListView.as_view(), name='article-list'),
    path('analytics/', AnalyticsAPIView.as_view(), name='analytics'),
    path('articles/<int:pk>/', ArticleDetailView.as_view(), name='article-detail'),
    path('articles/<int:pk>/heartbeat/', HeartbeatView.as_view(), name='article-heartbeat'),
    path('profile/', UserProfileView.as_view(), name='profile-detail'),
    path('interests/add/', AddInterestView.as_view(), name='add-interest')
]