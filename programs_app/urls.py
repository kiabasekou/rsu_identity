# urls.py - Routes API

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'programs', views.SocialProgramViewSet)
router.register(r'beneficiaries', views.BeneficiaryViewSet)
router.register(r'payments', views.PaymentViewSet)
router.register(r'vouchers', views.DigitalVoucherViewSet)

urlpatterns = [
    path('', include(router.urls)),
]