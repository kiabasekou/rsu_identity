# microservices/ml_service/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import aioredis
import asyncpg
from sklearn.externals import joblib
import numpy as np

app = FastAPI(title="RSU ML Service", version="1.0.0")

# Configuration
DATABASE_URL = "postgresql://user:password@postgres:5432/rsu_db"
REDIS_URL = "redis://redis:6379"

# Modèles Pydantic
class Person(BaseModel):
    id: str
    full_name: str
    date_of_birth: str
    gender: str
    address: Optional[dict] = None

class SimilarityRequest(BaseModel):
    person_a: Person
    person_b: Person

class SimilarityResponse(BaseModel):
    similarity_score: float
    name_score: float
    dob_score: float
    address_score: float
    confidence: float

class BatchDeduplicationRequest(BaseModel):
    persons: List[Person]
    threshold: float = 0.8

# Services
class MLDeduplicationService:
    def __init__(self):
        self.model = joblib.load('/models/deduplication_model.pkl')
        self.scaler = joblib.load('/models/feature_scaler.pkl')
    
    async def calculate_similarity(self, person_a: Person, person_b: Person) -> SimilarityResponse:
        """Calcul de similarité avec modèle ML optimisé"""
        
        # Extraction des features
        features = await self._extract_features(person_a, person_b)
        
        # Normalisation
        features_scaled = self.scaler.transform([features])
        
        # Prédiction
        similarity_score = self.model.predict_proba(features_scaled)[0][1]
        confidence = self.model.predict_proba(features_scaled).max()
        
        return SimilarityResponse(
            similarity_score=similarity_score,
            name_score=features[0],
            dob_score=features[1],
            address_score=features[2],
            confidence=confidence
        )
    
    async def _extract_features(self, person_a: Person, person_b: Person) -> List[float]:
        """Extraction des features pour ML"""
        
        # Feature engineering optimisé
        from difflib import SequenceMatcher
        from datetime import datetime
        
        # 1. Similarité nom (multiple algorithms)
        name_ratio = SequenceMatcher(None, person_a.full_name.lower(), person_b.full_name.lower()).ratio()
        
        # 2. Similarité date de naissance
        dob_a = datetime.fromisoformat(person_a.date_of_birth)
        dob_b = datetime.fromisoformat(person_b.date_of_birth)
        days_diff = abs((dob_a - dob_b).days)
        dob_score = max(0.0, 1.0 - (days_diff / 365.25))
        
        # 3. Similarité adresse géospatiale
        address_score = 0.0
        if person_a.address and person_b.address:
            # Implémentation géospatiale avec haversine
            address_score = await self._calculate_address_similarity(
                person_a.address, person_b.address)
        
        # 4. Features additionnelles
        gender_match = 1.0 if person_a.gender == person_b.gender else 0.0
        
        return [name_ratio, dob_score, address_score, gender_match]
    
    async def _calculate_address_similarity(self, addr_a: dict, addr_b: dict) -> float:
        """Calcul similarité géospatiale des adresses"""
        
        # Si coordonnées GPS disponibles
        if (addr_a.get('lat') and addr_a.get('lon') and 
            addr_b.get('lat') and addr_b.get('lon')):
            
            from math import radians, cos, sin, asin, sqrt
            
            def haversine(lon1, lat1, lon2, lat2):
                """Calcul distance haversine"""
                lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
                dlon = lon2 - lon1
                dlat = lat2 - lat1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                km = 6371 * c  # Rayon terre en km
                return km
            
            distance_km = haversine(
                addr_a['lon'], addr_a['lat'],
                addr_b['lon'], addr_b['lat']
            )
            
            # Score inversement proportionnel à la distance
            return max(0.0, 1.0 - (distance_km / 100.0))  # 0 à 100km
        
        # Fallback sur similarité textuelle
        addr_text_a = addr_a.get('text', '').lower()
        addr_text_b = addr_b.get('text', '').lower()
        
        return SequenceMatcher(None, addr_text_a, addr_text_b).ratio()

# Instance du service ML
ml_service = MLDeduplicationService()

# Endpoints FastAPI
@app.post("/similarity", response_model=SimilarityResponse)
async def calculate_similarity(request: SimilarityRequest):
    """Calcul de similarité entre deux personnes"""
    
    try:
        result = await ml_service.calculate_similarity(request.person_a, request.person_b)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur calcul similarité: {str(e)}")

@app.post("/batch-deduplication")
async def batch_deduplication(request: BatchDeduplicationRequest):
    """Déduplication en lot avec traitement parallèle"""
    
    try:
        persons = request.persons
        threshold = request.threshold
        
        # Traitement parallèle par chunks
        chunk_size = 10
        tasks = []
        
        for i in range(0, len(persons), chunk_size):
            chunk = persons[i:i + chunk_size]
            task = process_deduplication_chunk(chunk, persons, threshold)
            tasks.append(task)
        
        # Exécution parallèle
        results = await asyncio.gather(*tasks)
        
        # Agrégation résultats
        all_candidates = []
        for chunk_results in results:
            all_candidates.extend(chunk_results)
        
        return {
            "total_persons": len(persons),
            "candidates_found": len(all_candidates),
            "candidates": all_candidates
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur déduplication batch: {str(e)}")

async def process_deduplication_chunk(chunk: List[Person], all_persons: List[Person], threshold: float):
    """Traitement d'un chunk de déduplication"""
    
    candidates = []
    
    for person in chunk:
        for candidate in all_persons:
            if person.id != candidate.id:
                
                # Calcul similarité
                similarity = await ml_service.calculate_similarity(person, candidate)
                
                if similarity.similarity_score >= threshold:
                    candidates.append({
                        "person_a_id": person.id,
                        "person_b_id": candidate.id,
                        "similarity_score": similarity.similarity_score,
                        "confidence": similarity.confidence
                    })
    
    return candidates

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ml-deduplication"}

# Metrics endpoint pour monitoring
@app.get("/metrics")
async def get_metrics():
    # Implémentation métriques Prometheus
    return {"predictions_count": 0, "average_response_time": 0.0}