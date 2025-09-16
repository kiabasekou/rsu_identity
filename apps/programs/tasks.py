# apps/programs/tasks.py
from celery import shared_task
from django.utils import timezone
from decimal import Decimal
import logging
from .models import Payment, ProgramEnrollment
from .services import PaymentProcessor

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_payment_task(self, payment_id: str):
    """Traitement asynchrone d'un paiement"""
    
    try:
        payment = Payment.objects.get(id=payment_id)
        processor = PaymentProcessor()
        
        result = processor.process_payment_sync(payment)
        
        if result['success']:
            logger.info(f"Paiement {payment_id} traité avec succès")
            
            # Notification bénéficiaire si configurée
            send_payment_notification.delay(payment_id)
        else:
            logger.error(f"Échec paiement {payment_id}: {result.get('error_message')}")
            
    except Payment.DoesNotExist:
        logger.error(f"Paiement {payment_id} non trouvé")
        
    except Exception as exc:
        logger.error(f"Erreur traitement paiement {payment_id}: {exc}")
        
        # Retry avec backoff exponentiel
        countdown = 300 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

@shared_task
def send_payment_notification(payment_id: str):
    """Notification de paiement au bénéficiaire"""
    
    try:
        payment = Payment.objects.select_related(
            'enrollment__beneficiary__person'
        ).get(id=payment_id)
        
        beneficiary = payment.enrollment.beneficiary
        person = beneficiary.person
        
        # SMS notification si numéro disponible
        # Email notification si email disponible
        # Logique de notification à implémenter selon canaux disponibles
        
        logger.info(f"Notification envoyée pour paiement {payment_id}")
        
    except Exception as e:
        logger.error(f"Erreur notification paiement {payment_id}: {e}")

@shared_task
def generate_periodic_payments():
    """Génération périodique des paiements (tâche cron)"""
    
    try:
        from apps.programs.services import ProgramManagementService
        
        service = ProgramManagementService()
        service.process_periodic_payments()
        
        logger.info("Génération paiements périodiques terminée")
        
    except Exception as e:
        logger.error(f"Erreur génération paiements périodiques: {e}")

@shared_task
def reconcile_payments():
    """Réconciliation des paiements avec relevés bancaires"""
    
    try:
        # Logique de réconciliation
        # 1. Import des relevés bancaires/Mobile Money
        # 2. Matching avec paiements en cours
        # 3. Mise à jour statuts
        
        unreconciled_payments = Payment.objects.filter(
            reconciliation_status='PENDING',
            payment_status='COMPLETED',
            completed_at__lte=timezone.now() - timezone.timedelta(hours=24)
        )
        
        reconciled_count = 0
        
        for payment in unreconciled_payments:
            # Logique de réconciliation spécifique
            # (à implémenter selon sources de données disponibles)
            pass
        
        logger.info(f"Réconcilié {reconciled_count} paiements")
        
    except Exception as e:
        logger.error(f"Erreur réconciliation paiements: {e}")