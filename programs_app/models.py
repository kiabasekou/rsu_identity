from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
from decimal import Decimal

class SocialProgram(models.Model):
    """Programmes sociaux du gouvernement gabonais"""
    
    PROGRAM_TYPES = [
        ('CASH_TRANSFER', 'Transfert monétaire'),
        ('FOOD_ASSISTANCE', 'Aide alimentaire'),
        ('HEALTH_SUPPORT', 'Soutien santé'),
        ('EDUCATION_GRANT', 'Bourse éducation'),
        ('HOUSING_SUBSIDY', 'Subvention logement'),
        ('EMPLOYMENT_PROGRAM', 'Programme emploi'),
        ('DISABILITY_SUPPORT', 'Aide handicap'),
        ('ELDERLY_CARE', 'Soins personnes âgées'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'),
        ('ACTIVE', 'Actif'),
        ('SUSPENDED', 'Suspendu'),
        ('CLOSED', 'Fermé'),
        ('UNDER_REVIEW', 'En révision'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)  # Ex: RSU-001, ALI-002
    name = models.CharField(max_length=200)
    description = models.TextField()
    program_type = models.CharField(max_length=30, choices=PROGRAM_TYPES)
    
    # Configuration financière
    budget_total = models.DecimalField(max_digits=15, decimal_places=2)
    budget_allocated = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    amount_per_beneficiary = models.DecimalField(max_digits=10, decimal_places=2)
    payment_frequency = models.CharField(
        max_length=20,
        choices=[
            ('ONE_TIME', 'Paiement unique'),
            ('MONTHLY', 'Mensuel'),
            ('QUARTERLY', 'Trimestriel'),
            ('YEARLY', 'Annuel'),
        ]
    )
    
    # Période d'exécution
    start_date = models.DateField()
    end_date = models.DateField()
    registration_start = models.DateField()
    registration_end = models.DateField()
    
    # Ciblage géographique
    target_provinces = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    target_cities = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    is_nationwide = models.BooleanField(default=False)
    
    # Critères d'éligibilité
    min_age = models.PositiveIntegerField(null=True, blank=True)
    max_age = models.PositiveIntegerField(null=True, blank=True)
    target_gender = models.CharField(max_length=1, choices=[('M', 'Masculin'), ('F', 'Féminin'), ('A', 'Tous')], default='A')
    max_income_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    required_documents = ArrayField(models.CharField(max_length=100), default=list)
    
    # Configuration avancée - CORRIGÉ pour Django 5.x
    eligibility_rules = models.JSONField(default=dict)  # ← CORRIGÉ
    additional_criteria = models.JSONField(default=dict)  # ← CORRIGÉ
    
    # Statut et gestion
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    max_beneficiaries = models.PositiveIntegerField(null=True, blank=True)
    current_beneficiaries = models.PositiveIntegerField(default=0)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='created_programs')
    manager = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='managed_programs')
    
    # Coordination avec ministères
    responsible_ministry = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200)
    contact_phone = models.CharField(max_length=15)
    contact_email = models.EmailField()
    
    class Meta:
        db_table = 'programs_social_programs'
        indexes = [
            models.Index(fields=['code', 'status']),
            models.Index(fields=['program_type', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F('start_date')),
                name='end_date_after_start_date'
            ),
            models.CheckConstraint(
                check=models.Q(registration_end__gte=models.F('registration_start')),
                name='registration_end_after_start'
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def is_active(self):
        today = timezone.now().date()
        return (self.status == 'ACTIVE' and 
                self.start_date <= today <= self.end_date)

    @property
    def is_accepting_registrations(self):
        today = timezone.now().date()
        return (self.status == 'ACTIVE' and 
                self.registration_start <= today <= self.registration_end)

    @property
    def budget_remaining(self):
        return self.budget_total - self.budget_allocated

    @property
    def capacity_remaining(self):
        if self.max_beneficiaries:
            return self.max_beneficiaries - self.current_beneficiaries
        return None


class Beneficiary(models.Model):
    """Bénéficiaires des programmes sociaux"""
    
    BENEFICIARY_STATUS = [
        ('REGISTERED', 'Enregistré'),
        ('UNDER_REVIEW', 'En cours d\'évaluation'),
        ('APPROVED', 'Approuvé'),
        ('REJECTED', 'Rejeté'),
        ('ACTIVE', 'Actif'),
        ('SUSPENDED', 'Suspendu'),
        ('GRADUATED', 'Diplômé/Sorti'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary_number = models.CharField(max_length=20, unique=True)  # Numéro automatique
    
    # Liens
    person = models.ForeignKey('identity_app.PersonIdentity', on_delete=models.CASCADE)
    program = models.ForeignKey(SocialProgram, on_delete=models.CASCADE)
    
    # Statut d'inscription
    status = models.CharField(max_length=20, choices=BENEFICIARY_STATUS, default='REGISTERED')
    registration_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # Évaluation d'éligibilité
    eligibility_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    vulnerability_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    priority_ranking = models.PositiveIntegerField(null=True, blank=True)
    
    # Données spécifiques au programme
    monthly_payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_payments_received = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_payment_date = models.DateField(null=True, blank=True)
    
    # Suivi et monitoring
    household_visits = models.PositiveIntegerField(default=0)
    last_visit_date = models.DateField(null=True, blank=True)
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))
    
    # Documents et validation
    submitted_documents = ArrayField(models.CharField(max_length=100), default=list)
    missing_documents = ArrayField(models.CharField(max_length=100), default=list)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'En attente'),
            ('VERIFIED', 'Vérifié'),
            ('REJECTED', 'Rejeté'),
        ],
        default='PENDING'
    )
    
    # Métadonnées
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='registered_beneficiaries')
    approved_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True, related_name='approved_beneficiaries')
    case_worker = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True, related_name='assigned_beneficiaries')
    
    # Notes et historique - CORRIGÉ pour Django 5.x
    notes = models.TextField(blank=True)
    additional_data = models.JSONField(default=dict)  # ← CORRIGÉ
    
    class Meta:
        db_table = 'programs_beneficiaries'
        indexes = [
            models.Index(fields=['beneficiary_number']),
            models.Index(fields=['program', 'status']),
            models.Index(fields=['person', 'program']),
            models.Index(fields=['approval_date', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['person', 'program'],
                name='unique_person_per_program'
            ),
        ]

    def __str__(self):
        return f"{self.beneficiary_number} - {self.person.full_name}"

    @property
    def is_active(self):
        return self.status == 'ACTIVE'

    @property
    def days_in_program(self):
        if self.start_date:
            return (timezone.now().date() - self.start_date).days
        return 0


class Payment(models.Model):
    """Paiements aux bénéficiaires"""
    
    PAYMENT_STATUS = [
        ('PENDING', 'En attente'),
        ('PROCESSING', 'En traitement'),
        ('COMPLETED', 'Effectué'),
        ('FAILED', 'Échoué'),
        ('CANCELLED', 'Annulé'),
        ('REFUNDED', 'Remboursé'),
    ]
    
    PAYMENT_METHODS = [
        ('BANK_TRANSFER', 'Virement bancaire'),
        ('MOBILE_MONEY', 'Mobile money'),
        ('DIGITAL_VOUCHER', 'Bon numérique'),
        ('CASH', 'Espèces'),
        ('CHECK', 'Chèque'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_reference = models.CharField(max_length=30, unique=True)
    
    # Liens
    beneficiary = models.ForeignKey(Beneficiary, on_delete=models.CASCADE, related_name='payments')
    program = models.ForeignKey(SocialProgram, on_delete=models.CASCADE)
    
    # Détails du paiement
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='XAF')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=15, choices=PAYMENT_STATUS, default='PENDING')
    
    # Période couverte
    payment_period_start = models.DateField()
    payment_period_end = models.DateField()
    
    # Traitement
    initiated_date = models.DateTimeField(auto_now_add=True)
    processed_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Détails techniques
    external_transaction_id = models.CharField(max_length=100, blank=True)
    payment_provider = models.CharField(max_length=100, blank=True)
    fees = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    
    # Bénéficiaire final
    recipient_name = models.CharField(max_length=200)
    recipient_phone = models.CharField(max_length=15, blank=True)
    recipient_account = models.CharField(max_length=50, blank=True)
    
    # Métadonnées
    initiated_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='initiated_payments')
    approved_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True, related_name='approved_payments')
    failure_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'programs_payments'
        indexes = [
            models.Index(fields=['payment_reference']),
            models.Index(fields=['beneficiary', 'status']),
            models.Index(fields=['status', 'initiated_date']),
            models.Index(fields=['payment_period_start', 'payment_period_end']),
        ]

    def __str__(self):
        return f"{self.payment_reference} - {self.amount} XAF à {self.recipient_name}"


class DigitalVoucher(models.Model):
    """Bons numériques pour aide alimentaire/autres"""
    
    VOUCHER_STATUS = [
        ('ACTIVE', 'Actif'),
        ('USED', 'Utilisé'),
        ('EXPIRED', 'Expiré'),
        ('CANCELLED', 'Annulé'),
        ('SUSPENDED', 'Suspendu'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voucher_code = models.CharField(max_length=20, unique=True)
    qr_code = models.TextField()  # QR Code encodé
    
    # Liens
    beneficiary = models.ForeignKey(Beneficiary, on_delete=models.CASCADE, related_name='vouchers')
    program = models.ForeignKey(SocialProgram, on_delete=models.CASCADE)
    
    # Valeur et utilisation
    face_value = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_value = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='XAF')
    
    # Validité
    issue_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField()
    status = models.CharField(max_length=15, choices=VOUCHER_STATUS, default='ACTIVE')
    
    # Restrictions d'usage
    allowed_categories = ArrayField(models.CharField(max_length=100), default=list)  # ['food', 'medicine', 'education']
    allowed_merchants = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    geographic_restrictions = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    
    # Utilisation
    first_use_date = models.DateTimeField(null=True, blank=True)
    last_use_date = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    
    # Métadonnées
    issued_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='issued_vouchers')
    
    class Meta:
        db_table = 'programs_digital_vouchers'
        indexes = [
            models.Index(fields=['voucher_code']),
            models.Index(fields=['beneficiary', 'status']),
            models.Index(fields=['expiry_date', 'status']),
        ]

    def __str__(self):
        return f"Bon {self.voucher_code} - {self.face_value} XAF"

    @property
    def is_usable(self):
        return (self.status == 'ACTIVE' and 
                self.remaining_value > 0 and 
                timezone.now() < self.expiry_date)

    @property
    def usage_percentage(self):
        if self.face_value > 0:
            return float((self.face_value - self.remaining_value) / self.face_value * 100)
        return 0
