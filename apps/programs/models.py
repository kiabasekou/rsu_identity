# apps/programs/models.py
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.core.validators import MinValueValidator
from django.db.models import Q, UniqueConstraint
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid
import hashlib
import json
import base64
import io
import qrcode
from datetime import datetime

class Beneficiary(models.Model):
    """Bénéficiaire des programmes sociaux"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Actif'),
        ('SUSPENDED', 'Suspendu'),
        ('TERMINATED', 'Terminé'),
        ('PENDING', 'En attente'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey('identity.PersonIdentity', on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    registration_date = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    household_size = models.PositiveIntegerField(default=1)
    dependents_count = models.PositiveIntegerField(default=0)
    employment_status = models.CharField(max_length=50, null=True, blank=True)
    education_level = models.CharField(max_length=50, null=True, blank=True)
    health_status = models.CharField(max_length=50, null=True, blank=True)
    housing_type = models.CharField(max_length=50, null=True, blank=True)
    
    data_validation_date = models.DateTimeField(null=True, blank=True)
    data_validation_status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'En attente'), ('VALIDATED', 'Validé'), ('REJECTED', 'Rejeté')],
        default='PENDING'
    )
    validation_notes = models.TextField(blank=True)
    
    case_worker = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='beneficiaries_created')
    
    class Meta:
        db_table = 'programs_beneficiaries'
        indexes = [
            models.Index(fields=['status', 'registration_date']),
            models.Index(fields=['case_worker', 'status']),
        ]
    
    def __str__(self):
        # Vérifiez si person est non nul avant d'accéder à son attribut
        person_name = self.person.full_name if self.person else "Inconnu"
        return f"Bénéficiaire {person_name} ({self.status})"

class ProgramEnrollment(models.Model):
    """Inscription d'un bénéficiaire à un programme"""
    
    ENROLLMENT_STATUS = [
        ('ENROLLED', 'Inscrit'),
        ('WAITLISTED', 'Liste d\'attente'),
        ('REJECTED', 'Rejeté'),
        ('GRADUATED', 'Diplômé'),
        ('DROPPED_OUT', 'Abandon'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(Beneficiary, on_delete=models.CASCADE)
    program = models.ForeignKey('eligibility.SocialProgram', on_delete=models.CASCADE)
    
    enrollment_status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS, default='ENROLLED')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    monthly_benefit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount_received = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_frequency = models.CharField(max_length=20, default='MONTHLY')
    
    special_conditions = JSONField(blank=True, default=dict)
    compliance_status = models.CharField(
        max_length=20,
        choices=[('COMPLIANT', 'Conforme'), ('NON_COMPLIANT', 'Non conforme'), ('UNDER_REVIEW', 'En révision')],
        default='COMPLIANT'
    )
    
    last_evaluation_date = models.DateTimeField(null=True, blank=True)
    next_evaluation_date = models.DateTimeField(null=True, blank=True)
    graduation_readiness_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='enrollments_created')
    
    class Meta:
        db_table = 'programs_enrollments'
        indexes = [
            models.Index(fields=['enrollment_status', 'enrollment_date']),
            models.Index(fields=['program', 'enrollment_status']),
            models.Index(fields=['next_evaluation_date']),
        ]
        constraints = [
            UniqueConstraint(
                fields=['beneficiary', 'program'],
                condition=Q(enrollment_status__in=['ENROLLED', 'WAITLISTED']),
                name='unique_active_enrollment'
            ),
        ]
    
    def __str__(self):
        return f"Inscription de {self.beneficiary} au programme {self.program}"

class Payment(models.Model):
    """Paiements aux bénéficiaires"""
    
    PAYMENT_STATUS = [
        ('PENDING', 'En attente'),
        ('PROCESSING', 'En cours'),
        ('COMPLETED', 'Terminé'),
        ('FAILED', 'Échec'),
        ('CANCELLED', 'Annulé'),
        ('REFUNDED', 'Remboursé'),
    ]
    
    PAYMENT_METHODS = [
        ('MOBILE_MONEY', 'Mobile Money'),
        ('BANK_TRANSFER', 'Virement bancaire'),
        ('CASH', 'Espèces'),
        ('VOUCHER', 'Bon d\'achat'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(ProgramEnrollment, on_delete=models.CASCADE)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    
    payment_period_start = models.DateField()
    payment_period_end = models.DateField()
    
    reference_number = models.CharField(max_length=100, unique=True)
    external_transaction_id = models.CharField(max_length=100, null=True, blank=True)
    provider_reference = models.CharField(max_length=100, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    processing_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    reconciliation_status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'En attente'), ('RECONCILED', 'Réconcilié'), ('DISCREPANCY', 'Écart')],
        default='PENDING'
    )
    reconciliation_date = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='payments_created')
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'programs_payments'
        indexes = [
            models.Index(fields=['payment_status', 'created_at']),
            models.Index(fields=['enrollment', 'payment_status']),
            models.Index(fields=['reconciliation_status']),
            models.Index(fields=['payment_period_start', 'payment_period_end']),
        ]

    def __str__(self):
        return f"Paiement {self.reference_number} - {self.amount} FCFA"

class DigitalVoucher(models.Model):
    """Bons numériques pour services non-monétaires"""

    VOUCHER_TYPES = [
        ('FOOD', 'Alimentation'),
        ('HEALTH', 'Santé'),
        ('EDUCATION', 'Éducation'),
        ('TRANSPORT', 'Transport'),
        ('UTILITIES', 'Services publics'),
    ]

    VOUCHER_STATUS = [
        ('ACTIVE', 'Actif'),
        ('USED', 'Utilisé'),
        ('EXPIRED', 'Expiré'),
        ('CANCELLED', 'Annulé'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(ProgramEnrollment, on_delete=models.CASCADE)

    voucher_type = models.CharField(max_length=20, choices=VOUCHER_TYPES)
    voucher_value = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_value = models.DecimalField(max_digits=10, decimal_places=2)

    issued_date = models.DateTimeField(auto_now_add=True)
    expiration_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=VOUCHER_STATUS, default='ACTIVE')

    qr_code = models.TextField()
    security_hash = models.CharField(max_length=64)

    authorized_providers = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    usage_restrictions = JSONField(blank=True, default=dict)

    usage_history = JSONField(blank=True, default=list)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'programs_digital_vouchers'
        indexes = [
            models.Index(fields=['status', 'expiration_date']),
            models.Index(fields=['voucher_type', 'status']),
            models.Index(fields=['security_hash']),
        ]

    def generate_qr_code(self):
        """Génération QR code sécurisé"""
        payload = {
            'voucher_id': str(self.id),
            'value': float(self.voucher_value),
            'remaining': float(self.remaining_value),
            'expires': self.expiration_date.isoformat(),
            'type': self.voucher_type
        }
        
        payload_str = json.dumps(payload, sort_keys=True)
        security_key = settings.VOUCHER_SECRET_KEY
        self.security_hash = hashlib.sha256(
            (payload_str + security_key).encode()
        ).hexdigest()
        
        qr_data = f"RSU_VOUCHER|{payload_str}|{self.security_hash}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        buffer = io.BytesIO()
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img.save(buffer, format='PNG')
        
        self.qr_code = base64.b64encode(buffer.getvalue()).decode()
    
    def use_voucher(self, amount: Decimal, provider_id: str, transaction_details: dict):
        """Utilisation partielle ou totale du bon"""
        
        if self.status != 'ACTIVE':
            raise ValueError(f"Bon non actif: {self.status}")
        
        if amount > self.remaining_value:
            raise ValueError(f"Montant supérieur au solde: {amount} > {self.remaining_value}")
        
        if self.expiration_date < timezone.now():
            self.status = 'EXPIRED'
            self.save()
            raise ValueError("Bon expiré")
        
        if self.authorized_providers and provider_id not in self.authorized_providers:
            raise ValueError(f"Prestataire non autorisé: {provider_id}")
        
        self.remaining_value -= amount
        self.last_used_at = timezone.now()
        
        usage_entry = {
            'timestamp': timezone.now().isoformat(),
            'amount': float(amount),
            'provider_id': provider_id,
            'transaction_details': transaction_details
        }
        self.usage_history.append(usage_entry)
        
        if self.remaining_value <= 0:
            self.remaining_value = Decimal('0.00')
            self.status = 'USED'
        
        self.save()
        
        return self.remaining_value