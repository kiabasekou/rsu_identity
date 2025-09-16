# apps/programs/services.py
from django.db import transaction, models
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Optional
import logging
from .models import Beneficiary, ProgramEnrollment, Payment, DigitalVoucher
from apps.eligibility.models import SocialProgram, EligibilityEvaluation
from apps.identity.models import PersonIdentity

logger = logging.getLogger(__name__)

class ProgramManagementService:
    """Service principal de gestion des programmes sociaux"""
    
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        self.voucher_manager = VoucherManager()
    
    @transaction.atomic
    def enroll_beneficiary(
        self, 
        person: PersonIdentity, 
        program: SocialProgram,
        eligibility_evaluation: EligibilityEvaluation,
        enrollment_data: Dict
    ) -> ProgramEnrollment:
        """Inscription d'un bénéficiaire à un programme"""
        
        # 1. Vérification éligibilité
        if not eligibility_evaluation.is_eligible:
            raise ValueError("Personne non éligible au programme")
        
        # 2. Vérification capacité programme
        if not program.is_budget_available:
            raise ValueError("Budget programme épuisé")
        
        current_enrollments = ProgramEnrollment.objects.filter(
            program=program,
            enrollment_status='ENROLLED'
        ).count()
        
        if program.max_beneficiaries and current_enrollments >= program.max_beneficiaries:
            # Mise en liste d'attente
            return self._add_to_waitlist(person, program, eligibility_evaluation, enrollment_data)
        
        # 3. Création/récupération du bénéficiaire
        beneficiary = self._get_or_create_beneficiary(person, enrollment_data)
        
        # 4. Calcul montant bénéfice
        benefit_amount = self._calculate_benefit_amount(program, eligibility_evaluation, enrollment_data)
        
        # 5. Création inscription
        enrollment = ProgramEnrollment.objects.create(
            beneficiary=beneficiary,
            program=program,
            enrollment_status='ENROLLED',
            start_date=enrollment_data.get('start_date', timezone.now().date()),
            monthly_benefit_amount=benefit_amount,
            payment_frequency=program.payment_frequency,
            special_conditions=enrollment_data.get('special_conditions', {}),
            next_evaluation_date=self._calculate_next_evaluation_date(program)
        )
        
        # 6. Mise à jour compteurs programme
        program.current_beneficiaries += 1
        program.allocated_budget += benefit_amount * self._get_payment_multiplier(program)
        program.save()
        
        # 7. Création du premier paiement si nécessaire
        if program.program_type == 'CASH_TRANSFER':
            self._schedule_initial_payment(enrollment)
        elif program.program_type == 'VOUCHER':
            self._issue_initial_vouchers(enrollment)
        
        logger.info(f"Inscription réussie: {person.nip} -> {program.code}")
        
        return enrollment
    
    def _get_or_create_beneficiary(self, person: PersonIdentity, enrollment_data: Dict) -> Beneficiary:
        """Création ou récupération d'un bénéficiaire"""
        
        beneficiary, created = Beneficiary.objects.get_or_create(
            person=person,
            defaults={
                'monthly_income': enrollment_data.get('monthly_income'),
                'household_size': enrollment_data.get('household_size', 1),
                'dependents_count': enrollment_data.get('dependents_count', 0),
                'employment_status': enrollment_data.get('employment_status'),
                'education_level': enrollment_data.get('education_level'),
                'health_status': enrollment_data.get('health_status'),
                'housing_type': enrollment_data.get('housing_type'),
                'data_validation_status': 'VALIDATED',
                'data_validation_date': timezone.now(),
                'created_by': enrollment_data.get('created_by')
            }
        )
        
        if not created:
            # Mise à jour des données si plus récentes
            update_fields = []
            for field in ['monthly_income', 'household_size', 'employment_status']:
                new_value = enrollment_data.get(field)
                if new_value and getattr(beneficiary, field) != new_value:
                    setattr(beneficiary, field, new_value)
                    update_fields.append(field)
            
            if update_fields:
                beneficiary.last_update = timezone.now()
                beneficiary.save(update_fields=update_fields + ['last_update'])
        
        return beneficiary
    
    def _calculate_benefit_amount(
        self, 
        program: SocialProgram, 
        eligibility_evaluation: EligibilityEvaluation,
        enrollment_data: Dict
    ) -> Decimal:
        """Calcul du montant du bénéfice selon critères"""
        
        base_amount = program.benefit_amount
        
        if not base_amount:
            return Decimal('0')
        
        # Ajustements selon score d'éligibilité
        eligibility_score = eligibility_evaluation.eligibility_score
        if eligibility_score >= 90:
            multiplier = Decimal('1.2')  # +20% pour très éligible
        elif eligibility_score >= 80:
            multiplier = Decimal('1.1')  # +10% pour hautement éligible
        else:
            multiplier = Decimal('1.0')  # montant de base
        
        # Ajustements selon taille ménage
        household_size = enrollment_data.get('household_size', 1)
        if household_size > 5:
            multiplier += Decimal('0.1')  # +10% pour familles nombreuses
        elif household_size > 3:
            multiplier += Decimal('0.05')  # +5% pour familles moyennes
        
        # Plafond et plancher
        adjusted_amount = base_amount * multiplier
        max_amount = base_amount * Decimal('1.5')  # Plafond +50%
        min_amount = base_amount * Decimal('0.8')  # Plancher -20%
        
        return min(max_amount, max(min_amount, adjusted_amount))
    
    def process_periodic_payments(self, program: SocialProgram = None):
        """Traitement périodique des paiements"""
        
        # Récupération des inscriptions actives
        enrollments_query = ProgramEnrollment.objects.filter(
            enrollment_status='ENROLLED',
            program__is_active=True
        ).select_related('beneficiary__person', 'program')
        
        if program:
            enrollments_query = enrollments_query.filter(program=program)
        
        # Filtrage selon fréquence de paiement et dernière date
        today = timezone.now().date()
        due_enrollments = []
        
        for enrollment in enrollments_query:
            if self._is_payment_due(enrollment, today):
                due_enrollments.append(enrollment)
        
        logger.info(f"Traitement {len(due_enrollments)} paiements dus")
        
        # Traitement par batches
        batch_size = 100
        for i in range(0, len(due_enrollments), batch_size):
            batch = due_enrollments[i:i + batch_size]
            self._process_payment_batch(batch)
    
    def _is_payment_due(self, enrollment: ProgramEnrollment, today) -> bool:
        """Vérification si un paiement est dû"""
        
        # Récupération du dernier paiement
        last_payment = Payment.objects.filter(
            enrollment=enrollment,
            payment_status='COMPLETED'
        ).order_by('-payment_period_end').first()
        
        if not last_payment:
            # Premier paiement
            return True
        
        # Calcul prochaine échéance selon fréquence
        frequency = enrollment.payment_frequency
        last_period_end = last_payment.payment_period_end
        
        from dateutil.relativedelta import relativedelta
        
        if frequency == 'MONTHLY':
            next_due_date = last_period_end + relativedelta(months=1)
        elif frequency == 'QUARTERLY':
            next_due_date = last_period_end + relativedelta(months=3)
        elif frequency == 'ANNUAL':
            next_due_date = last_period_end + relativedelta(years=1)
        else:
            return False
        
        return today >= next_due_date
    
    @transaction.atomic
    def _process_payment_batch(self, enrollments: List[ProgramEnrollment]):
        """Traitement d'un batch de paiements"""
        
        for enrollment in enrollments:
            try:
                payment = self.payment_processor.create_payment(enrollment)
                self.payment_processor.process_payment_async(payment)
                
            except Exception as e:
                logger.error(f"Erreur paiement pour {enrollment.id}: {e}")
                # Continuer avec les autres paiements

class PaymentProcessor:
    """Processeur de paiements multi-canaux"""
    
    def __init__(self):
        self.providers = {
            'MOBILE_MONEY': MobileMoneyProvider(),
            'BANK_TRANSFER': BankTransferProvider(),
            'CASH': CashProvider(),
        }
    
    @transaction.atomic
    def create_payment(self, enrollment: ProgramEnrollment) -> Payment:
        """Création d'un ordre de paiement"""
        
        # Détermination de la période de paiement
        period_start, period_end = self._calculate_payment_period(enrollment)
        
        # Génération référence unique
        reference = self._generate_payment_reference(enrollment, period_start)
        
        # Détermination méthode de paiement préférée
        payment_method = self._determine_payment_method(enrollment.beneficiary)
        
        payment = Payment.objects.create(
            enrollment=enrollment,
            amount=enrollment.monthly_benefit_amount,
            payment_method=payment_method,
            payment_period_start=period_start,
            payment_period_end=period_end,
            reference_number=reference,
            created_by=self._get_system_user()
        )
        
        return payment
    
    def process_payment_async(self, payment: Payment):
        """Traitement asynchrone du paiement"""
        from .tasks import process_payment_task
        
        process_payment_task.delay(payment.id)
    
    def process_payment_sync(self, payment: Payment) -> Dict:
        """Traitement synchrone du paiement"""
        
        provider = self.providers.get(payment.payment_method)
        if not provider:
            raise ValueError(f"Méthode de paiement non supportée: {payment.payment_method}")
        
        try:
            # Mise à jour statut
            payment.payment_status = 'PROCESSING'
            payment.processed_at = timezone.now()
            payment.save()
            
            # Traitement via le provider
            result = provider.process_payment(payment)
            
            # Mise à jour selon résultat
            if result['success']:
                payment.payment_status = 'COMPLETED'
                payment.completed_at = timezone.now()
                payment.external_transaction_id = result.get('transaction_id')
                payment.provider_reference = result.get('provider_reference')
                payment.processing_fee = Decimal(str(result.get('fee', 0)))
            else:
                payment.payment_status = 'FAILED'
                payment.notes = result.get('error_message', 'Erreur inconnue')
            
            payment.save()
            
            return result
            
        except Exception as e:
            payment.payment_status = 'FAILED'
            payment.notes = str(e)
            payment.save()
            
            logger.error(f"Erreur traitement paiement {payment.id}: {e}")
            raise
    
    def _determine_payment_method(self, beneficiary: Beneficiary) -> str:
        """Détermination de la méthode de paiement préférée"""
        
        # Logique de sélection basée sur profil bénéficiaire
        # 1. Préférence explicite si disponible
        # 2. Disponibilité Mobile Money (zones urbaines)
        # 3. Fallback sur espèces
        
        person = beneficiary.person
        
        # Zone urbaine -> Mobile Money privilégié
        if person.administrative_division in ['LIBREVILLE', 'PORT_GENTIL']:
            return 'MOBILE_MONEY'
        
        # Compte bancaire disponible
        # (logique à implémenter selon données disponibles)
        
        # Default: espèces
        return 'CASH'

# Providers de paiement
class MobileMoneyProvider:
    """Provider Mobile Money (Orange Money, Moov Money)"""
    
    def process_payment(self, payment: Payment) -> Dict:
        """Traitement paiement Mobile Money"""
        
        # Récupération numéro téléphone bénéficiaire
        phone_number = self._get_phone_number(payment.enrollment.beneficiary)
        
        if not phone_number:
            return {
                'success': False,
                'error_message': 'Numéro de téléphone non disponible'
            }
        
        # Appel API Mobile Money
        try:
            # Simulation appel API
            import random
            
            # 90% de succès en simulation
            if random.random() < 0.9:
                return {
                    'success': True,
                    'transaction_id': f"MM_{payment.reference_number}",
                    'provider_reference': f"OM{random.randint(100000, 999999)}",
                    'fee': 500.0  # 500 FCFA de frais
                }
            else:
                return {
                    'success': False,
                    'error_message': 'Échec transaction Mobile Money'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error_message': f'Erreur API Mobile Money: {str(e)}'
            }
    
    def _get_phone_number(self, beneficiary: Beneficiary) -> Optional[str]:
        """Récupération numéro téléphone bénéficiaire"""
        # Logique d'extraction du numéro selon données disponibles
        return "+24101234567"  # Simulation

class BankTransferProvider:
    """Provider virements bancaires"""
    
    def process_payment(self, payment: Payment) -> Dict:
        """Traitement virement bancaire"""
        
        # Simulation traitement bancaire
        return {
            'success': True,
            'transaction_id': f"BANK_{payment.reference_number}",
            'provider_reference': f"VIR{timezone.now().strftime('%Y%m%d%H%M%S')}",
            'fee': 1000.0  # 1000 FCFA de frais bancaires
        }

class CashProvider:
    """Provider paiement espèces (points de distribution)"""
    
    def process_payment(self, payment: Payment) -> Dict:
        """Préparation paiement espèces"""
        
        # Pour les espèces, "traitement" = préparation pour distribution
        return {
            'success': True,
            'transaction_id': f"CASH_{payment.reference_number}",
            'provider_reference': f"DIST{timezone.now().strftime('%Y%m%d')}",
            'fee': 0.0  # Pas de frais directs
        }

class VoucherManager:
    """Gestionnaire de bons numériques"""
    
    def issue_vouchers(
        self, 
        enrollment: ProgramEnrollment, 
        voucher_configs: List[Dict]
    ) -> List[DigitalVoucher]:
        """Émission de bons numériques"""
        
        vouchers = []
        
        for config in voucher_configs:
            voucher = DigitalVoucher.objects.create(
                enrollment=enrollment,
                voucher_type=config['type'],
                voucher_value=config['value'],
                remaining_value=config['value'],
                expiration_date=config['expiration_date'],
                authorized_providers=config.get('authorized_providers', []),
                usage_restrictions=config.get('restrictions', {})
            )
            
            # Génération QR code sécurisé
            voucher.generate_qr_code()
            voucher.save()
            
            vouchers.append(voucher)
        
        return vouchers
    
    def validate_voucher_usage(
        self, 
        qr_code_data: str, 
        provider_id: str, 
        amount: Decimal
    ) -> Dict:
        """Validation utilisation bon numérique"""
        
        try:
            # Décodage QR code
            parts = qr_code_data.split('|')
            if len(parts) != 3 or parts[0] != 'RSU_VOUCHER':
                return {'valid': False, 'error': 'QR code invalide'}
            
            import json
            import hashlib
            
            payload_str = parts[1]
            provided_hash = parts[2]
            
            # Vérification hash sécurisé
            security_key = settings.VOUCHER_SECRET_KEY
            expected_hash = hashlib.sha256(
                (payload_str + security_key).encode()
            ).hexdigest()
            
            if provided_hash != expected_hash:
                return {'valid': False, 'error': 'QR code falsifié'}
            
            # Extraction données
            payload = json.loads(payload_str)
            voucher_id = payload['voucher_id']
            
            # Récupération et validation du bon
            voucher = DigitalVoucher.objects.get(id=voucher_id)
            
            if voucher.status != 'ACTIVE':
                return {'valid': False, 'error': f'Bon non actif: {voucher.status}'}
            
            if voucher.expiration_date < timezone.now():
                voucher.status = 'EXPIRED'
                voucher.save()
                return {'valid': False, 'error': 'Bon expiré'}
            
            if amount > voucher.remaining_value:
                return {
                    'valid': False, 
                    'error': f'Montant supérieur au solde: {amount} > {voucher.remaining_value}'
                }
            
            if voucher.authorized_providers and provider_id not in voucher.authorized_providers:
                return {'valid': False, 'error': 'Prestataire non autorisé'}
            
            return {
                'valid': True,
                'voucher': voucher,
                'remaining_value': voucher.remaining_value,
                'voucher_type': voucher.voucher_type
            }
            
        except DigitalVoucher.DoesNotExist:
            return {'valid': False, 'error': 'Bon non trouvé'}
        except Exception as e:
            logger.error(f"Erreur validation voucher: {e}")
            return {'valid': False, 'error': 'Erreur validation'}
    
    @transaction.atomic
    def use_voucher(
        self, 
        voucher: DigitalVoucher, 
        amount: Decimal, 
        provider_id: str,
        transaction_details: Dict
    ) -> Dict:
        """Utilisation effective du bon"""
        
        try:
            remaining = voucher.use_voucher(amount, provider_id, transaction_details)
            
            return {
                'success': True,
                'amount_used': float(amount),
                'remaining_value': float(remaining),
                'status': voucher.status
            }
            
        except ValueError as e:
            return {
                'success': False,
                'error': str(e)
            }