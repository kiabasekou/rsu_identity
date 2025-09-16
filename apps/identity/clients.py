# apps/identity/clients.py
import httpx
import asyncio
from django.conf import settings
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class MLServiceClient:
    """Client pour service ML FastAPI"""
    
    def __init__(self):
        self.base_url = settings.ML_SERVICE_URL
        self.timeout = httpx.Timeout(30.0)
    
    async def calculate_similarity_async(self, person_a_data: dict, person_b_data: dict) -> Dict:
        """Calcul de similarité asynchrone"""
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/similarity",
                    json={
                        "person_a": person_a_data,
                        "person_b": person_b_data
                    }
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                logger.error(f"Erreur service ML: {e}")
                raise
    
    def calculate_similarity_sync(self, person_a_data: dict, person_b_data: dict) -> Dict:
        """Version synchrone pour compatibilité Django"""
        
        return asyncio.run(self.calculate_similarity_async(person_a_data, person_b_data))
    
    async def batch_deduplication_async(self, persons_data: List[dict], threshold: float = 0.8) -> Dict:
        """Déduplication en lot asynchrone"""
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:  # 5min timeout
            try:
                response = await client.post(
                    f"{self.base_url}/batch-deduplication",
                    json={
                        "persons": persons_data,
                        "threshold": threshold
                    }
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                logger.error(f"Erreur batch déduplication: {e}")
                raise

# Integration dans le service Django
class EnhancedDeduplicationService(DeduplicationService):
    """Service de déduplication enrichi avec ML externe"""
    
    def __init__(self):
        super().__init__()
        self.ml_client = MLServiceClient()
    
    def find_potential_duplicates(self, person: PersonIdentity) -> List[DeduplicationCandidate]:
        """Recherche avec service ML externe"""
        
        # 1. Pre-filtering avec Django ORM (rapide)
        similar_persons = PersonIdentity.objects.filter(
            full_name__trigram_similar=person.full_name
        ).exclude(id=person.id)[:50]
        
        candidates = []
        
        # 2. Calcul précis avec service ML
        person_data = self._person_to_dict(person)
        
        for candidate in similar_persons:
            candidate_data = self._person_to_dict(candidate)
            
            try:
                # Appel service ML
                ml_result = self.ml_client.calculate_similarity_sync(person_data, candidate_data)
                
                if ml_result['similarity_score'] >= self.similarity_threshold:
                    dedup_candidate = DeduplicationCandidate.objects.create(
                        person_a=person,
                        person_b=candidate,
                        similarity_score=ml_result['similarity_score'],
                        name_similarity=ml_result['name_score'],
                        dob_similarity=ml_result['dob_score'],
                        address_similarity=ml_result['address_score'],
                        ml_model_version="external_v1.0",
                        features_used=ml_result
                    )
                    candidates.append(dedup_candidate)
                    
            except Exception as e:
                logger.error(f"Erreur ML pour candidat {candidate.id}: {e}")
                # Fallback sur méthode originale
                continue
        
        return candidates
    
    def _person_to_dict(self, person: PersonIdentity) -> dict:
        """Conversion PersonIdentity vers dict pour service ML"""
        
        return {
            "id": str(person.id),
            "full_name": person.full_name,
            "date_of_birth": person.date_of_birth.isoformat(),
            "gender": person.gender,
            "address": person.primary_address
        }