# apps/surveys/models.py
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import UniqueConstraint, Q, Avg, Count
from django.utils import timezone
from decimal import Decimal
import uuid
from datetime import timedelta

# Import des modèles pour éviter les dépendances circulaires à l'intérieur des méthodes
# Ces modèles sont requis pour les ForeignKeys et les QuerySets
# Il est fortement recommandé d'avoir un fichier `models.py` dans chaque app.
# Pour l'exemple, nous incluons ici un modèle de session manquant.
class SurveySession(models.Model):
    """Session d'enquête pour un bénéficiaire et un enquêteur"""
    
    SESSION_STATUS = [
        ('IN_PROGRESS', 'En cours'),
        ('COMPLETED', 'Terminée'),
        ('SYNCED', 'Synchronisée'),
        ('VALIDATED', 'Validée'),
        ('REJECTED', 'Rejetée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey('surveys.SurveyTemplate', on_delete=models.PROTECT)
    beneficiary = models.ForeignKey('programs.Beneficiary', on_delete=models.CASCADE)
    surveyor = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='IN_PROGRESS')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), 
                                          validators=[MinValueValidator(0), MaxValueValidator(100)])
    data_quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), 
                                             validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    class Meta:
        db_table = 'surveys_sessions'
        indexes = [
            models.Index(fields=['surveyor', 'status']),
            models.Index(fields=['beneficiary']),
        ]

    def __str__(self):
        return f"Session {self.id} par {self.surveyor.username}"

class SurveyTemplate(models.Model):
    """Modèles d'enquête configurables"""
    
    SURVEY_TYPES = [
        ('HOUSEHOLD', 'Enquête ménage'),
        ('INDIVIDUAL', 'Enquête individuelle'),
        ('MONITORING', 'Suivi programme'),
        ('EVALUATION', 'Évaluation impact'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    version = models.CharField(max_length=20, default='1.0')
    survey_type = models.CharField(max_length=20, choices=SURVEY_TYPES)
    
    # Configuration questionnaire
    questions_config = JSONField()
    validation_rules = JSONField(default=dict)
    skip_logic = JSONField(default=dict)
    
    # Métadonnées
    description = models.TextField()
    estimated_duration_minutes = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    # Paramètres de déploiement
    target_regions = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    required_accuracy_meters = models.PositiveIntegerField(default=10)
    offline_capable = models.BooleanField(default=True)

    class Meta:
        db_table = 'surveys_templates'
        indexes = [
            models.Index(fields=['survey_type', 'is_active']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            UniqueConstraint(
                fields=['name', 'version'],
                name='unique_survey_version'
            ),
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"

class SurveyResponse(models.Model):
    """Réponses aux questions d'enquête"""
    
    QUESTION_TYPES = [
        ('TEXT', 'Texte libre'),
        ('NUMBER', 'Nombre'),
        ('INTEGER', 'Entier'),
        ('SELECT', 'Choix unique'),
        ('MULTISELECT', 'Choix multiples'),
        ('BOOLEAN', 'Oui/Non'),
        ('DATE', 'Date'),
        ('DATETIME', 'Date et heure'),
        ('GPS', 'Coordonnées GPS'),
        ('PHOTO', 'Photo'),
        ('AUDIO', 'Enregistrement audio'),
        ('SIGNATURE', 'Signature'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(SurveySession, on_delete=models.CASCADE, related_name='responses')

    # Question et réponse
    question_id = models.CharField(max_length=100)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    question_text = models.TextField()

    # Valeurs selon type
    text_value = models.TextField(null=True, blank=True)
    numeric_value = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    integer_value = models.BigIntegerField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    date_value = models.DateField(null=True, blank=True)
    datetime_value = models.DateTimeField(null=True, blank=True)
    json_value = JSONField(null=True, blank=True)

    # Métadonnées de collecte
    answered_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_skipped = models.BooleanField(default=False)
    skip_reason = models.CharField(max_length=100, null=True, blank=True)

    # Validation et qualité
    validation_status = models.CharField(
        max_length=20,
        choices=[('VALID', 'Valide'), ('INVALID', 'Invalide'), ('WARNING', 'Avertissement')],
        default='VALID'
    )
    validation_messages = ArrayField(models.TextField(), blank=True, default=list)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, default=Decimal('0.00'))

    class Meta:
        db_table = 'surveys_responses'
        indexes = [
            models.Index(fields=['session', 'question_id']),
            models.Index(fields=['question_type', 'validation_status']),
            models.Index(fields=['answered_at']),
        ]
        constraints = [
            UniqueConstraint(
                fields=['session', 'question_id'],
                name='unique_response_per_question'
            ),
        ]
    
    def __str__(self):
        return f"Réponse à {self.question_id} pour session {self.session.id}"

    def get_typed_value(self):
        """Récupération de la valeur typée selon le type de question"""
        
        if self.is_skipped:
            return None
        
        type_mapping = {
            'TEXT': self.text_value,
            'NUMBER': self.numeric_value,
            'INTEGER': self.integer_value,
            'SELECT': self.text_value,
            'MULTISELECT': self.json_value,
            'BOOLEAN': self.boolean_value,
            'DATE': self.date_value,
            'DATETIME': self.datetime_value,
            'GPS': self.json_value,
            'PHOTO': self.text_value,
            'AUDIO': self.text_value,
            'SIGNATURE': self.text_value,
        }
        
        return type_mapping.get(self.question_type)

class MediaFile(models.Model):
    """Fichiers média collectés (photos, audio, signatures)"""
    
    MEDIA_TYPES = [
        ('PHOTO', 'Photo'),
        ('AUDIO', 'Audio'),
        ('VIDEO', 'Vidéo'),
        ('SIGNATURE', 'Signature'),
        ('DOCUMENT', 'Document'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE, related_name='media_files')

    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES)
    original_filename = models.CharField(max_length=255)
    file_size_bytes = models.BigIntegerField()
    mime_type = models.CharField(max_length=100)

    local_path = models.CharField(max_length=500, null=True, blank=True)
    cloud_url = models.URLField(null=True, blank=True)
    storage_provider = models.CharField(max_length=50, null=True, blank=True)

    captured_at = models.DateTimeField(auto_now_add=True)
    device_info = JSONField(blank=True, default=dict)
    gps_coordinates = JSONField(null=True, blank=True)

    uploaded_at = models.DateTimeField(null=True, blank=True)
    upload_status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'En attente'), ('UPLOADING', 'En cours'), ('COMPLETED', 'Terminé'), ('FAILED', 'Échec')],
        default='PENDING'
    )

    processed_at = models.DateTimeField(null=True, blank=True)
    processing_results = JSONField(blank=True, default=dict)

    class Meta:
        db_table = 'surveys_media_files'
        indexes = [
            models.Index(fields=['response', 'media_type']),
            models.Index(fields=['upload_status', 'captured_at']),
        ]

    def __str__(self):
        return f"Média {self.media_type} pour la réponse {self.response.id}"


class DataQualityCheck(models.Model):
    """Contrôles qualité automatisés"""

    CHECK_TYPES = [
        ('COMPLETENESS', 'Complétude'),
        ('CONSISTENCY', 'Cohérence'),
        ('ACCURACY', 'Précision'),
        ('VALIDITY', 'Validité'),
        ('UNIQUENESS', 'Unicité'),
        ('TIMELINESS', 'Temporalité'),
    ]

    SEVERITY_LEVELS = [
        ('INFO', 'Information'),
        ('WARNING', 'Avertissement'),
        ('ERROR', 'Erreur'),
        ('CRITICAL', 'Critique'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(SurveySession, on_delete=models.CASCADE, related_name='quality_checks')

    check_type = models.CharField(max_length=20, choices=CHECK_TYPES)
    check_name = models.CharField(max_length=100)
    description = models.TextField()

    passed = models.BooleanField()
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    affected_questions = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    error_details = JSONField(blank=True, default=dict)
    recommendations = JSONField(blank=True, default=list)

    checked_at = models.DateTimeField(auto_now_add=True)
    check_version = models.CharField(max_length=20, default='1.0')

    class Meta:
        db_table = 'surveys_quality_checks'
        indexes = [
            models.Index(fields=['session', 'check_type', 'severity']),
            models.Index(fields=['passed', 'severity']),
        ]

    def __str__(self):
        return f"Contrôle {self.check_name} pour session {self.session.id}"

class SurveyorProfile(models.Model):
    """Profil étendu des enquêteurs"""
    
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='surveyor_profile')

    employee_id = models.CharField(max_length=50, unique=True)
    supervisor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='supervised_surveyors')
    regions_assigned = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    survey_types_authorized = ArrayField(models.CharField(max_length=50), blank=True, default=list)

    certification_level = models.CharField(
        max_length=20,
        choices=[('JUNIOR', 'Junior'), ('SENIOR', 'Senior'), ('EXPERT', 'Expert'), ('SUPERVISOR', 'Superviseur')],
        default='JUNIOR'
    )
    certifications = JSONField(blank=True, default=list)
    last_training_date = models.DateField(null=True, blank=True)

    total_surveys_completed = models.PositiveIntegerField(default=0)
    average_quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    average_completion_time = models.DurationField(null=True, blank=True)

    preferred_language = models.CharField(max_length=10, default='fr')
    offline_sync_frequency = models.PositiveIntegerField(default=60)
    auto_backup_enabled = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    device_info = JSONField(blank=True, default=dict)

    class Meta:
        db_table = 'surveys_surveyor_profiles'
        indexes = [
            models.Index(fields=['is_active', 'certification_level']),
            models.Index(fields=['supervisor', 'is_active']),
        ]
    
    def __str__(self):
        return f"Profil de {self.user.username}"
    
    def update_performance_metrics(self):
        """Mise à jour des métriques de performance"""
        
        # Le code d'origine faisait une importation locale, déplacée en haut du fichier.
        
        completed_sessions = self.user.surveysession_set.filter(
            status__in=['COMPLETED', 'SYNCED', 'VALIDATED']
        )
        
        if not completed_sessions.exists():
            self.total_surveys_completed = 0
            self.average_quality_score = Decimal('0.00')
            self.average_completion_time = None
            self.save(update_fields=['total_surveys_completed', 'average_quality_score', 'average_completion_time'])
            return
            
        metrics = completed_sessions.aggregate(
            total_count=Count('id'),
            avg_quality=Avg('data_quality_score'),
            # Calcul de la durée moyenne en minutes
            avg_duration_minutes=Avg('duration_minutes')
        )
        
        self.total_surveys_completed = metrics.get('total_count', 0)
        self.average_quality_score = metrics.get('avg_quality', Decimal('0.00'))
        
        avg_minutes = metrics.get('avg_duration_minutes')
        if avg_minutes is not None:
            self.average_completion_time = timedelta(minutes=avg_minutes)
        else:
            self.average_completion_time = None
        
        self.save(update_fields=['total_surveys_completed', 'average_quality_score', 'average_completion_time'])