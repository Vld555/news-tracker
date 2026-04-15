from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SourceViewSet, ArticleListView, AnalyticsAPIView, ArticleDetailView, HeartbeatView, SourceListCreateView, UserProfileView, UserRegistrationView

router = DefaultRouter()
router.register(r'sources', SourceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('register/', UserRegistrationView.as_view(), name='user-register'), # НОВЫЙ ПУТЬ
    path('articles/', ArticleListView.as_view(), name='article-list'),
    path('analytics/', AnalyticsAPIView.as_view(), name='analytics'),
    path('articles/<int:pk>/', ArticleDetailView.as_view(), name='article-detail'),
    path('articles/<int:pk>/heartbeat/', HeartbeatView.as_view(), name='article-heartbeat'),
    path('sources/', SourceListCreateView.as_view(), name='source-list-create'),
    path('profile/', UserProfileView.as_view(), name='profile-detail'),
    path('sources/', SourceListCreateView.as_view(), name='source-list'),
]