from django.urls import path
from . import views

urlpatterns = [
    # Routes surveys à implémenter
    path('', views.survey_list, name='survey_list'),
]
