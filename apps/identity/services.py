# apps/identity/services.py
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
from typing import List, Optional
import logging
from .models import PersonIdentity, DeduplicationCandidate
from .tasks import sync_with_rbpp_async, run_deduplication_batch
from rbpp_connector.clients import RBPPAPIClient

logger = logging.getLogger(__name__)

class IdentityService:
    """Service principal de gestion des identités"""
    
    def __init__(self):
        self.rbpp_client = RBPPAPIClient()
        self.cache_timeout = getattr(settings, 'IDENTITY_CACHE_TIMEOUT', 3600)
    
    @transaction.atomic
    def create_person_identity(self, identity_data: dict, created_by_user) -> PersonIdentity:
        """Création d'identité avec validation et déduplication automatique"""
        
        # 1. Validation des données
        self._validate_identity_data(identity_data)
        
        # 2. Vérification existence NIP
        nip = identity_data.get('nip')
        if nip and PersonIdentity.objects.filter(nip=nip).exists():
            raise ValueError(f"NIP {nip} déjà existant")
        
        # 3. Création de l'identité
        identity = PersonIdentity.objects.create(
            **identity_data,
            created_by=created_by_user,
            updated_by=created_by_user
        )
        
        # 4. Déclenchement déduplication asynchrone
        run_deduplication_batch.delay(person_id=identity.id)
        
        # 5. Synchronisation RBPP si NIP fourni
        if nip:
            sync_with_rbpp_async.delay(person_id=identity.id, nip=nip)
        
        logger.info(f"Identité créée: {identity.id} pour NIP: {nip}")
        return identity
    
    def search_persons(self, query: str, filters: dict = None, limit: int = 50) -> List[PersonIdentity]:
        """Recherche optimisée avec full-text search et filtres"""
        
        cache_key = f"person_search:{hash(query)}:{hash(str(filters))}:{limit}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        queryset = PersonIdentity.objects.select_related('created_by', 'updated_by')
        
        # Recherche textuelle avec PostgreSQL FTS
        if query:
            queryset = queryset.filter(search_vector=query)
        
        # Application des filtres
        if filters:
            if filters.get('administrative_division'):
                queryset = queryset.filter(
                    administrative_division=filters['administrative_division']
                )
            
            if filters.get('verification_status'):
                queryset = queryset.filter(
                    verification_status=filters['verification_status']
                )
            
            if filters.get('date_range'):
                start_date, end_date = filters['date_range']
                queryset = queryset.filter(
                    created_at__date__range=[start_date, end_date]
                )
        
        # Tri par pertinence puis par date
        queryset = queryset.order_by('-data_quality_score', '-created_at')
        
        results = list(queryset[:limit])
        cache.set(cache_key, results, self.cache_timeout)
        
        return results
    
    def get_family_members(self, person_id: str, relationship_types: List[str] = None) -> List[dict]:
        """Récupération des membres de la famille avec optimisation"""
        
        cache_key = f"family_members:{person_id}:{hash(str(relationship_types))}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        from .models import FamilyRelationship
        
        base_query = FamilyRelationship.objects.filter(
            models.Q(person_a_id=person_id) | models.Q(person_b_id=person_id),
            is_active=True
        ).select_related('person_a', 'person_b')
        
        if relationship_types:
            base_query = base_query.filter(relationship_type__in=relationship_types)
        
        family_members = []
        for relationship in base_query:
            # Déterminer l'autre personne dans la relation
            other_person = (
                relationship.person_b if str(relationship.person_a.id) == person_id 
                else relationship.person_a
            )
            
            family_members.append({
                'person': other_person,
                'relationship_type': relationship.relationship_type,
                'start_date': relationship.start_date,
                'confidence_score': float(relationship.confidence_score)
            })
        
        cache.set(cache_key, family_members, self.cache_timeout)
        return family_members
    
    def _validate_identity_data(self, data: dict) -> None:
        """Validation métier des données d'identité"""
        
        required_fields = ['full_name', 'date_of_birth', 'gender']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            raise ValueError(f"Champs obligatoires manquants: {', '.join(missing_fields)}")
        
        # Validation format NIP gabonais
        nip = data.get('nip')
        if nip and not self._validate_nip_format(nip):
            raise ValueError(f"Format NIP invalide: {nip}")
    
    def _validate_nip_format(self, nip: str) -> bool:
        """Validation format NIP gabonais"""
        # Implémentation selon spécifications RBPP
        import re
        pattern = r'^[0-9]{13}$'  # Format à ajuster selon spécifications
        return bool(re.match(pattern, nip))

class DeduplicationService:
    """Service de déduplication avec ML"""
    
    def __init__(self):
        self.ml_model = self._load_ml_model()
        self.similarity_threshold = 0.8
    
    def find_potential_duplicates(self, person: PersonIdentity) -> List[DeduplicationCandidate]:
        """Recherche de doublons potentiels avec ML"""
        
        # 1. Recherche par similarité de nom (pre-filtering)
        similar_names = PersonIdentity.objects.filter(
            full_name__trigram_similar=person.full_name
        ).exclude(id=person.id)[:100]  # Limiter pour performance
        
        candidates = []
        
        for candidate in similar_names:
            # 2. Calcul des scores de similarité
            similarity_scores = self._calculate_similarity_scores(person, candidate)
            
            # 3. Prédiction ML
            overall_score = self.ml_model.predict_similarity(similarity_scores)
            
            if overall_score >= self.similarity_threshold:
                dedup_candidate = DeduplicationCandidate.objects.create(
                    person_a=person,
                    person_b=candidate,
                    similarity_score=overall_score,
                    name_similarity=similarity_scores['name'],
                    dob_similarity=similarity_scores['dob'],
                    address_similarity=similarity_scores['address'],
                    phone_similarity=similarity_scores['phone'],
                    ml_model_version=self.ml_model.version,
                    features_used=similarity_scores
                )
                candidates.append(dedup_candidate)
        
        return candidates
    
    def _calculate_similarity_scores(self, person1: PersonIdentity, person2: PersonIdentity) -> dict:
        """Calcul des scores de similarité par dimension"""
        
        from difflib import SequenceMatcher
        from datetime import datetime
        
        # Similarité nom (Jaro-Winkler approximation)
        name_score = SequenceMatcher(None, person1.full_name.lower(), person2.full_name.lower()).ratio()
        
        # Similarité date de naissance
        dob_score = 0.0
        if person1.date_of_birth and person2.date_of_birth:
            days_diff = abs((person1.date_of_birth - person2.date_of_birth).days)
            dob_score = max(0.0, 1.0 - (days_diff / 365.0))  # Décroît avec l'âge
        
        # Similarité adresse
        address_score = 0.0
        if (person1.primary_address and person2.primary_address and 
            person1.administrative_division == person2.administrative_division):
            address_score = 0.7  # Score de base si même division administrative
        
        # Similarité téléphone (si disponible)
        phone_score = 0.0
        # Implémentation selon disponibilité des données téléphone
        
        return {
            'name': name_score,
            'dob': dob_score,
            'address': address_score,
            'phone': phone_score
        }
    
    def _load_ml_model(self):
        """Chargement du modèle ML de déduplication"""
        # Implémentation du chargement du modèle
        # Peut être un modèle scikit-learn sérialisé ou TensorFlow/PyTorch
        class MockMLModel:
            version = "1.0"
            
            def predict_similarity(self, features):
                # Combinaison pondérée simple (à remplacer par modèle réel)
                return (
                    features['name'] * 0.4 +
                    features['dob'] * 0.3 +
                    features['address'] * 0.2 +
                    features['phone'] * 0.1
                )
        
        return MockMLModel()
    