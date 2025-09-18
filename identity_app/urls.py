#5. urls.py - Routes API

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'persons', views.PersonIdentityViewSet)
router.register(r'deduplication', views.DeduplicationCandidateViewSet)
router.register(r'relationships', views.FamilyRelationshipViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
