# apps/eligibility/models.py
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class SocialProgram(models.Model):
    """Programmes sociaux avec règles d'éligibilité configurables"""
    
    PROGRAM_TYPES = [
        ('CASH_TRANSFER', 'Transfert monétaire'),
        ('IN_KIND', 'Aide en nature'),
        ('SERVICE', 'Service social'),
        ('VOUCHER', 'Bon d\'achat'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    program_type = models.CharField(max_length=20, choices=PROGRAM_TYPES)
    
    # Budget et capacité
    total_budget = models.DecimalField(max_digits=15, decimal_places=2)
    allocated_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    max_beneficiaries = models.PositiveIntegerField(null=True, blank=True)
    current_beneficiaries = models.PositiveIntegerField(default=0)
    
    # Périodes d'activité
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    # Configuration paiements
    benefit_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    payment_frequency = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', 'Mensuel'),
            ('QUARTERLY', 'Trimestriel'),
            ('ANNUAL', 'Annuel'),
            ('ONE_TIME', 'Unique'),
        ],
        default='MONTHLY'
    )
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    class Meta:
        db_table = 'eligibility_programs'
        indexes = [
            models.Index(fields=['is_active', 'start_date', 'end_date']),
            models.Index(fields=['program_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @property
    def budget_utilization_rate(self):
        """Taux d'utilisation du budget"""
        if self.total_budget == 0:
            return 0
        return float(self.allocated_budget / self.total_budget)
    
    @property
    def is_budget_available(self):
        """Vérification disponibilité budget"""
        return self.allocated_budget < self.total_budget

class EligibilityRule(models.Model):
    """Règles d'éligibilité configurables"""
    
    RULE_TYPES = [
        ('DEMOGRAPHIC', 'Démographique'),
        ('INCOME', 'Revenus'),
        ('GEOGRAPHIC', 'Géographique'),
        ('HOUSEHOLD', 'Composition ménage'),
        ('HEALTH', 'État de santé'),
        ('EDUCATION', 'Éducation'),
        ('EMPLOYMENT', 'Emploi'),
    ]
    
    OPERATORS = [
        ('EQ', 'Égal'),
        ('NE', 'Différent'),
        ('GT', 'Supérieur'),
        ('GTE', 'Supérieur ou égal'),
        ('LT', 'Inférieur'),
        ('LTE', 'Inférieur ou égal'),
        ('IN', 'Dans la liste'),
        ('NOT_IN', 'Pas dans la liste'),
        ('CONTAINS', 'Contient'),
        ('BETWEEN', 'Entre'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(SocialProgram, on_delete=models.CASCADE, related_name='eligibility_rules')
    
    # Configuration de la règle
    rule_name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    field_name = models.CharField(max_length=100)  # Champ à évaluer
    operator = models.CharField(max_length=10, choices=OPERATORS)
    expected_value = JSONField()  # Valeur attendue (peut être liste, nombre, etc.)
    
    # Pondération et priorité
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    priority = models.PositiveIntegerField(default=1)
    is_mandatory = models.BooleanField(default=True)
    
    # Métadonnées
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'eligibility_rules'
        indexes = [
            models.Index(fields=['program', 'is_active', 'priority']),
            models.Index(fields=['rule_type', 'is_active']),
        ]
        ordering = ['priority', 'rule_name']
    
    def __str__(self):
        return f"{self.rule_name} ({self.program.code})"

class VulnerabilityScore(models.Model):
    """Scores de vulnérabilité calculés"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.OneToOneField('identity.PersonIdentity', on_delete=models.CASCADE)
    
    # Scores par dimension
    overall_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    demographic_score = models.DecimalField(max_digits=5, decimal_places=2)
    economic_score = models.DecimalField(max_digits=5, decimal_places=2)
    social_score = models.DecimalField(max_digits=5, decimal_places=2)
    health_score = models.DecimalField(max_digits=5, decimal_places=2)
    geographic_score = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Facteurs contributeurs
    contributing_factors = JSONField()  # Liste des facteurs avec poids
    
    # Métadonnées calcul
    calculated_at = models.DateTimeField(auto_now=True)
    calculation_version = models.CharField(max_length=20)
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Classification
    vulnerability_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Faible'),
            ('MODERATE', 'Modérée'),
            ('HIGH', 'Élevée'),
            ('CRITICAL', 'Critique'),
        ]
    )
    
    class Meta:
        db_table = 'eligibility_vulnerability_scores'
        indexes = [
            models.Index(fields=['overall_score', 'vulnerability_level']),
            models.Index(fields=['calculated_at']),
        ]

class EligibilityEvaluation(models.Model):
    """Évaluations d'éligibilité avec résultats détaillés"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey('identity.PersonIdentity', on_delete=models.CASCADE)
    program = models.ForeignKey(SocialProgram, on_delete=models.CASCADE)
    
    # Résultats évaluation
    is_eligible = models.BooleanField()
    eligibility_score = models.DecimalField(max_digits=5, decimal_places=2)  # Score composite
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Détails par règle
    rule_evaluations = JSONField()  # Résultat détaillé par règle
    failed_mandatory_rules = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    
    # Recommandations
    recommendation = models.TextField(blank=True)
    alternative_programs = ArrayField(models.UUIDField(), blank=True, default=list)
    
    # Métadonnées
    evaluated_at = models.DateTimeField(auto_now_add=True)
    evaluated_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True)
    evaluation_version = models.CharField(max_length=20)
    
    # Données contextuelles utilisées
    evaluation_context = JSONField()  # Snapshot des données utilisées
    
    class Meta:
        db_table = 'eligibility_evaluations'
        indexes = [
            models.Index(fields=['person', 'program', 'evaluated_at']),
            models.Index(fields=['is_eligible', 'eligibility_score']),
            models.Index(fields=['evaluated_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['person', 'program'],
                condition=models.Q(is_eligible=True),
                name='unique_eligible_per_program'
            ),
        ]