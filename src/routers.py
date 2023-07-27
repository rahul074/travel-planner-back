from rest_framework import routers
from django.urls import path, include

from .accounts.viewsets import UserViewSet

router = routers.DefaultRouter()

# user
router.register(r'users', UserViewSet, basename='v1_auth')


urlpatterns = [
    path('api/v1/', include(router.urls)),
    ]
