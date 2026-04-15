from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.views.generic import TemplateView 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('news.urls')),
    path('api/v1/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # НОВЫЕ ПУТИ ДЛЯ ФРОНТЕНДА (HTML)
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('index.html', TemplateView.as_view(template_name='index.html')),
    path('login.html', TemplateView.as_view(template_name='login.html')),
    path('profile.html', TemplateView.as_view(template_name='profile.html')),
    path('dashboard.html', TemplateView.as_view(template_name='dashboard.html')),
    path('article.html', TemplateView.as_view(template_name='article.html')),
]