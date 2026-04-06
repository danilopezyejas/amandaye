from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import SociosViewSet

router = DefaultRouter()
router.register(r'socios', SociosViewSet, basename='socios')

urlpatterns = [
    path('', include(router.urls)),
]
