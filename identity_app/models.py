from django.db import models
from django.core.validators import RegexValidator, MinLengthValidator
from django.utils import timezone
import uuid
import json
from decimal import Decimal

class PersonIdentity(models.Model):
    """Identité unique d'une personne dans le système RSU"""
    
    GENDER_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
        ('O', 'Autre'),
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('SINGLE', 'Célibataire'),
        ('MARRIED', 'Marié(e)'),
        ('DIVORCED', 'Divorcé(e)'),
        ('WIDOWED', 'Veuf/Veuve'),
        ('SEPARATED', 'Séparé(e)'),
    ]
    
    # Identifiant unique
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Informations personnelles
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField()
    birth_place = models.CharField(max_length=200)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES)
    
    # Documents officiels
    national_id = models.CharField(
        max_length=20, 
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d{12}$',
                message='Le numéro de CNI doit contenir exactement 12 chiffres'
            )
        ]
    )
    passport_number = models.CharField(max_length=20, blank=True, null=True)
    birth_certificate_number = models.CharField(max_length=50, blank=True)
    
    # Contact
    phone_number = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+241\d{8}$',
                message='Format: +241XXXXXXXX'
            )
        ]
    )
    email = models.EmailField(blank=True, null=True)
    
    # Adresse
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10, blank=True)
    
    # Coordonnées GPS
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_accuracy = models.FloatField(null=True, blank=True)
    
    # Informations socio-économiques
    occupation = models.CharField(max_length=200, blank=True)
    education_level = models.CharField(max_length=100, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    household_size = models.PositiveIntegerField(default=1)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='created_identities')
    
    # Statut de validation
    is_validated = models.BooleanField(default=False)
    validated_at = models.DateTimeField(null=True, blank=True)
    validated_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True, related_name='validated_identities')
    
    # Données RBPP
    rbpp_synchronized = models.BooleanField(default=False)
    rbpp_last_sync = models.DateTimeField(null=True, blank=True)
    rbpp_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'identity_persons'
        indexes = [
            models.Index(fields=['national_id']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['first_name', 'last_name']),
            models.Index(fields=['birth_date']),
            models.Index(fields=['city', 'province']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.national_id})"

    @property
    def full_name(self):
        names = [self.first_name]
        if self.middle_name:
            names.append(self.middle_name)
        names.append(self.last_name)
        return ' '.join(names)

    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))


class DeduplicationCandidate(models.Model):
    """Candidats potentiels de déduplication"""
    
    MATCH_TYPES = [
        ('EXACT', 'Correspondance exacte'),
        ('HIGH', 'Probabilité élevée'),
        ('MEDIUM', 'Probabilité moyenne'),
        ('LOW', 'Probabilité faible'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'En attente'),
        ('CONFIRMED', 'Confirmé comme doublon'),
        ('REJECTED', 'Rejeté'),
        ('MERGED', 'Fusionné'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person1 = models.ForeignKey(PersonIdentity, on_delete=models.CASCADE, related_name='dedup_as_person1')
    person2 = models.ForeignKey(PersonIdentity, on_delete=models.CASCADE, related_name='dedup_as_person2')
    
    # Score de similarité
    similarity_score = models.DecimalField(max_digits=5, decimal_places=4)
    match_type = models.CharField(max_length=10, choices=MATCH_TYPES)
    
    # Détails de la correspondance - CORRIGÉ pour SQLite
    matching_fields = models.TextField(blank=True)  # JSON string
    conflicting_fields = models.TextField(blank=True)  # JSON string
    confidence_factors = models.JSONField(default=dict)
    
    # Statut de résolution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Métadonnées
    detected_at = models.DateTimeField(auto_now_add=True)
    algorithm_version = models.CharField(max_length=20)
    
    class Meta:
        db_table = 'identity_deduplication_candidates'
        indexes = [
            models.Index(fields=['similarity_score', 'match_type']),
            models.Index(fields=['status', 'detected_at']),
        ]

    def __str__(self):
        return f"Déduplication {self.person1.full_name} ↔ {self.person2.full_name} ({self.similarity_score})"

    # Helpers pour gérer les listes comme JSON
    def get_matching_fields(self):
        return json.loads(self.matching_fields) if self.matching_fields else []
    
    def set_matching_fields(self, fields_list):
        self.matching_fields = json.dumps(fields_list)
    
    def get_conflicting_fields(self):
        return json.loads(self.conflicting_fields) if self.conflicting_fields else []
    
    def set_conflicting_fields(self, fields_list):
        self.conflicting_fields = json.dumps(fields_list)


class FamilyRelationship(models.Model):
    """Relations familiales entre personnes"""
    
    RELATIONSHIP_TYPES = [
        ('PARENT', 'Parent'),
        ('CHILD', 'Enfant'),
        ('SPOUSE', 'Époux/Épouse'),
        ('SIBLING', 'Frère/Sœur'),
        ('GRANDPARENT', 'Grand-parent'),
        ('GRANDCHILD', 'Petit-enfant'),
        ('UNCLE_AUNT', 'Oncle/Tante'),
        ('NEPHEW_NIECE', 'Neveu/Nièce'),
        ('COUSIN', 'Cousin(e)'),
        ('GUARDIAN', 'Tuteur légal'),
        ('WARD', 'Pupille'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person1 = models.ForeignKey(PersonIdentity, on_delete=models.CASCADE, related_name='relationships_as_person1')
    person2 = models.ForeignKey(PersonIdentity, on_delete=models.CASCADE, related_name='relationships_as_person2')
    relationship_type = models.CharField(max_length=20, choices=RELATIONSHIP_TYPES)
    
    # Métadonnées
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True)
    supporting_documents = models.TextField(blank=True)  # JSON string
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='created_relationships')
    
    class Meta:
        db_table = 'identity_family_relationships'
        indexes = [
            models.Index(fields=['person1', 'relationship_type']),
            models.Index(fields=['person2', 'relationship_type']),
        ]

    def __str__(self):
        return f"{self.person1.full_name} → {self.get_relationship_type_display()} → {self.person2.full_name}"

    def get_supporting_documents(self):
        return json.loads(self.supporting_documents) if self.supporting_documents else []
    
    def set_supporting_documents(self, docs_list):
        self.supporting_documents = json.dumps(docs_list)
