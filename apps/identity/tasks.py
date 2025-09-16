# apps/identity/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging
from .models import PersonIdentity, DeduplicationCandidate
from .services import DeduplicationService
from rbpp_connector.clients import RBPPAPIClient

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_with_rbpp_async(self, person_id: str, nip: str):
    """Synchronisation asynchrone avec RBPP"""
    
    try:
        person = PersonIdentity.objects.get(id=person_id)
        rbpp_client = RBPPAPIClient()
        
        # Récupération des données RBPP
        rbpp_data = rbpp_client.get_person_by_nip(nip)
        
        if rbpp_data:
            # Mise à jour des données avec RBPP
            person.verification_status = 'VERIFIED'
            person.data_quality_score = 95.0  # Score élevé car validé RBPP
            
            # Enrichissement si données manquantes
            if not person.place_of_birth and rbpp_data.get('place_of_birth'):
                person.place_of_birth = rbpp_data['place_of_birth']
            
            person.save()
            logger.info(f"Synchronisation RBPP réussie pour {person_id}")
        
    except PersonIdentity.DoesNotExist:
        logger.error(f"Personne {person_id} non trouvée pour sync RBPP")
        
    except Exception as exc:
        logger.error(f"Erreur sync RBPP pour {person_id}: {exc}")
        
        # Retry avec backoff exponentiel
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

@shared_task(bind=True)
def run_deduplication_batch(self, person_id: str = None, batch_size: int = 100):
    """Traitement de déduplication par batch"""
    
    dedup_service = DeduplicationService()
    
    if person_id:
        # Déduplication pour une personne spécifique
        try:
            person = PersonIdentity.objects.get(id=person_id)
            candidates = dedup_service.find_potential_duplicates(person)
            
            logger.info(f"Trouvé {len(candidates)} candidats de déduplication pour {person_id}")
            
            # Notification si doublons à haute probabilité
            high_prob_candidates = [c for c in candidates if c.similarity_score > 0.9]
            if high_prob_candidates:
                notify_deduplication_reviewers.delay(person_id, len(high_prob_candidates))
                
        except PersonIdentity.DoesNotExist:
            logger.error(f"Personne {person_id} non trouvée pour déduplication")
    else:
        # Traitement batch des personnes non traitées
        unprocessed_persons = PersonIdentity.objects.filter(
            verification_status='PENDING'
        )[:batch_size]
        
        for person in unprocessed_persons:
            dedup_service.find_potential_duplicates(person)

@shared_task
def notify_deduplication_reviewers(person_id: str, candidates_count: int):
    """Notification des réviseurs pour doublons haute probabilité"""
    
    try:
        person = PersonIdentity.objects.get(id=person_id)
        
        subject = f"Doublons détectés - {person.full_name}"
        message = f"""
        {candidates_count} doublons potentiels détectés pour:
        - Nom: {person.full_name}
        - NIP: {person.nip}
        - ID: {person_id}
        
        Révision manuelle requise dans l'interface d'administration.
        """
        
        reviewer_emails = settings.DEDUPLICATION_REVIEWERS_EMAILS
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=reviewer_emails,
            fail_silently=False
        )
        
        logger.info(f"Notification envoyée pour {candidates_count} doublons de {person_id}")
        
    except Exception as e:
        logger.error(f"Erreur notification déduplication: {e}")

@shared_task
def cleanup_old_deduplication_candidates():
    """Nettoyage périodique des candidats de déduplication traités"""
    
    from django.utils import timezone
    from datetime import timedelta
    
    # Suppression des candidats rejetés de plus de 30 jours
    cutoff_date = timezone.now() - timedelta(days=30)
    
    deleted_count = DeduplicationCandidate.objects.filter(
        status='REJECTED',
        reviewed_at__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f"Nettoyé {deleted_count} candidats de déduplication")