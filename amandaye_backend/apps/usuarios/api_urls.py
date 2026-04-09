from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import SociosViewSet, MeView

router = DefaultRouter()
router.register(r'socios', SociosViewSet, basename='socios')

urlpatterns = [
    path('me/', MeView.as_view(), name='api_me'),
    path('', include(router.urls)),
]
