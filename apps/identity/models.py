# apps/identity/models.py
from django.db import models
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.indexes import GinIndex, GistIndex
from django.contrib.gis.db import models as gis_models
import uuid

class PersonIdentity(models.Model):
    """Modèle principal des identités avec optimisations performance"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nip = models.CharField(max_length=20, unique=True, db_index=True)
    external_id = models.CharField(max_length=50, null=True, blank=True)
    
    # Informations personnelles
    full_name = models.CharField(max_length=200, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(db_index=True)
    place_of_birth = models.CharField(max_length=100, null=True)
    gender = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
    nationality = models.CharField(max_length=3, default='GAB')
    marital_status = models.CharField(max_length=20, null=True)
    
    # Adressage avec géolocalisation
    primary_address = JSONField(null=True, blank=True)
    gps_coordinates = gis_models.PointField(null=True, blank=True, srid=4326)
    administrative_division = models.CharField(max_length=50, null=True, db_index=True)
    
    # Métadonnées système
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    data_quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    verification_status = models.CharField(
        max_length=20, 
        choices=[('PENDING', 'Pending'), ('VERIFIED', 'Verified'), ('REJECTED', 'Rejected')],
        default='PENDING',
        db_index=True
    )
    
    # Audit et traçabilité
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='created_identities')
    updated_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='updated_identities')
    version = models.PositiveIntegerField(default=1)
    
    # Champs de recherche optimisés
    search_vector = models.GeneratedField(
        expression=models.func.to_tsvector('french', models.F('full_name')),
        output_field=models.TextField(),
        db_persist=True
    )
    
    class Meta:
        db_table = 'identity_persons'
        indexes = [
            # Index composite pour requêtes fréquentes
            models.Index(fields=['verification_status', 'created_at']),
            models.Index(fields=['administrative_division', 'verification_status']),
            
            # Index GIN pour recherche textuelle
            GinIndex(fields=['search_vector']),
            
            # Index GiST pour recherche géospatiale
            GistIndex(fields=['gps_coordinates']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(data_quality_score__gte=0.0) & models.Q(data_quality_score__lte=100.0),
                name='valid_quality_score'
            ),
        ]
    
    def __str__(self):
        return f"{self.full_name} ({self.nip})"
    
    def save(self, *args, **kwargs):
        # Auto-increment version sur mise à jour
        if self.pk:
            self.version += 1
        super().save(*args, **kwargs)

class FamilyRelationship(models.Model):
    """Relations familiales optimisées pour performances"""
    
    RELATIONSHIP_TYPES = [
        ('PARENT', 'Parent'),
        ('CHILD', 'Enfant'),
        ('SPOUSE', 'Conjoint'),
        ('SIBLING', 'Frère/Sœur'),
        ('GUARDIAN', 'Tuteur'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person_a = models.ForeignKey(PersonIdentity, on_delete=models.CASCADE, related_name='relationships_as_a')
    person_b = models.ForeignKey(PersonIdentity, on_delete=models.CASCADE, related_name='relationships_as_b')
    relationship_type = models.CharField(max_length=20, choices=RELATIONSHIP_TYPES)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'identity_family_relationships'
        indexes = [
            models.Index(fields=['person_a', 'relationship_type', 'is_active']),
            models.Index(fields=['person_b', 'relationship_type', 'is_active']),
        ]
        constraints = [
            # Éviter relations circulaires directes
            models.CheckConstraint(
                check=~models.Q(person_a=models.F('person_b')),
                name='no_self_relationship'
            ),
        ]

class DeduplicationCandidate(models.Model):
    """Candidats de déduplication avec scoring ML"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person_a = models.ForeignKey(PersonIdentity, on_delete=models.CASCADE, related_name='dedup_as_a')
    person_b = models.ForeignKey(PersonIdentity, on_delete=models.CASCADE, related_name='dedup_as_b')
    similarity_score = models.DecimalField(max_digits=5, decimal_places=4)  # 0.0000 - 1.0000
    
    # Scores par dimension
    name_similarity = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    dob_similarity = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    address_similarity = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    phone_similarity = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    
    # Métadonnées ML
    ml_model_version = models.CharField(max_length=20)
    features_used = JSONField()
    
    # Statut traitement
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'En attente'),
            ('REVIEWING', 'En révision'),
            ('CONFIRMED', 'Confirmé doublon'),
            ('REJECTED', 'Pas un doublon'),
        ],
        default='PENDING'
    )
    
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'identity_deduplication_candidates'
        indexes = [
            models.Index(fields=['similarity_score', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['person_a', 'person_b'],
                name='unique_dedup_pair'
            ),
        ]