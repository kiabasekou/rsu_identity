# 7. apps.py - Configuration de l'app

from django.apps import AppConfig

class IdentityAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'identity_app'
    verbose_name = 'Gestion des Identités'
