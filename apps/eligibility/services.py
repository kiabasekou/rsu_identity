# apps/eligibility/services.py
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
from typing import Dict, List, Any, Tuple
import logging
from decimal import Decimal
from .models import SocialProgram, EligibilityRule, EligibilityEvaluation, VulnerabilityScore
from apps.identity.models import PersonIdentity

logger = logging.getLogger(__name__)

class EligibilityEngine:
    """Moteur d'évaluation d'éligibilité avec règles configurables"""
    
    def __init__(self):
        self.cache_timeout = getattr(settings, 'ELIGIBILITY_CACHE_TIMEOUT', 1800)  # 30min
        self.vulnerability_calculator = VulnerabilityCalculator()
    
    @transaction.atomic
    def evaluate_person_eligibility(
        self, 
        person: PersonIdentity, 
        program: SocialProgram,
        context_data: Dict = None
    ) -> EligibilityEvaluation:
        """Évaluation complète d'éligibilité pour une personne et un programme"""
        
        # 1. Vérification cache
        cache_key = f"eligibility:{person.id}:{program.id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # 2. Collecte des données contextuelles
        evaluation_context = self._collect_evaluation_context(person, context_data)
        
        # 3. Calcul du score de vulnérabilité si nécessaire
        vulnerability_score = self._get_or_calculate_vulnerability_score(person)
        
        # 4. Évaluation des règles
        rule_results = self._evaluate_rules(program, evaluation_context, vulnerability_score)
        
        # 5. Calcul score composite et décision finale
        eligibility_result = self._calculate_final_eligibility(program, rule_results)
        
        # 6. Génération recommandations
        recommendations = self._generate_recommendations(
            person, program, rule_results, eligibility_result
        )
        
        # 7. Création de l'évaluation
        evaluation = EligibilityEvaluation.objects.create(
            person=person,
            program=program,
            is_eligible=eligibility_result['is_eligible'],
            eligibility_score=eligibility_result['score'],
            confidence_level=eligibility_result['confidence'],
            rule_evaluations=rule_results,
            failed_mandatory_rules=eligibility_result['failed_mandatory'],
            recommendation=recommendations['recommendation'],
            alternative_programs=recommendations['alternatives'],
            evaluation_context=evaluation_context,
            evaluation_version="1.0"
        )
        
        # 8. Mise en cache
        cache.set(cache_key, evaluation, self.cache_timeout)
        
        logger.info(f"Évaluation éligibilité: {person.id} -> {program.code} = {eligibility_result['is_eligible']}")
        
        return evaluation
    
    def _collect_evaluation_context(self, person: PersonIdentity, additional_data: Dict = None) -> Dict:
        """Collecte des données nécessaires à l'évaluation"""
        
        context = {
            # Données démographiques
            'age': self._calculate_age(person.date_of_birth),
            'gender': person.gender,
            'marital_status': getattr(person, 'marital_status', None),
            'administrative_division': person.administrative_division,
            
            # Localisation
            'gps_coordinates': {
                'lat': person.gps_coordinates.y if person.gps_coordinates else None,
                'lon': person.gps_coordinates.x if person.gps_coordinates else None,
            },
            
            # Composition familiale
            'family_size': self._get_family_size(person),
            'dependents_count': self._get_dependents_count(person),
            'household_head': self._is_household_head(person),
            
            # Données socio-économiques (si disponibles)
            'monthly_income': additional_data.get('monthly_income') if additional_data else None,
            'employment_status': additional_data.get('employment_status') if additional_data else None,
            'education_level': additional_data.get('education_level') if additional_data else None,
            'health_status': additional_data.get('health_status') if additional_data else None,
            'housing_type': additional_data.get('housing_type') if additional_data else None,
            
            # Métadonnées
            'evaluation_date': timezone.now().isoformat(),
            'data_completeness': self._calculate_data_completeness(person, additional_data)
        }
        
        return context
    
    def _evaluate_rules(
        self, 
        program: SocialProgram, 
        context: Dict, 
        vulnerability_score: VulnerabilityScore
    ) -> Dict:
        """Évaluation de toutes les règles du programme"""
        
        rules = program.eligibility_rules.filter(is_active=True).order_by('priority')
        rule_results = {}
        
        for rule in rules:
            try:
                result = self._evaluate_single_rule(rule, context, vulnerability_score)
                rule_results[str(rule.id)] = {
                    'rule_name': rule.rule_name,
                    'rule_type': rule.rule_type,
                    'is_mandatory': rule.is_mandatory,
                    'weight': float(rule.weight),
                    'passed': result['passed'],
                    'score': result['score'],
                    'details': result['details']
                }
            except Exception as e:
                logger.error(f"Erreur évaluation règle {rule.id}: {e}")
                rule_results[str(rule.id)] = {
                    'rule_name': rule.rule_name,
                    'passed': False,
                    'score': 0.0,
                    'error': str(e)
                }
        
        return rule_results
    
    def _evaluate_single_rule(
        self, 
        rule: EligibilityRule, 
        context: Dict, 
        vulnerability_score: VulnerabilityScore
    ) -> Dict:
        """Évaluation d'une règle individuelle"""
        
        # Récupération de la valeur à évaluer
        actual_value = self._get_context_value(rule.field_name, context, vulnerability_score)
        expected_value = rule.expected_value
        operator = rule.operator
        
        # Évaluation selon l'opérateur
        passed = self._apply_operator(actual_value, expected_value, operator)
        
        # Calcul du score (0-100)
        score = 100.0 if passed else 0.0
        
        # Pour les règles numériques, score graduel possible
        if operator in ['GT', 'GTE', 'LT', 'LTE'] and actual_value is not None:
            score = self._calculate_gradual_score(actual_value, expected_value, operator)
        
        return {
            'passed': passed,
            'score': score,
            'details': {
                'actual_value': actual_value,
                'expected_value': expected_value,
                'operator': operator
            }
        }
    
    def _apply_operator(self, actual: Any, expected: Any, operator: str) -> bool:
        """Application des opérateurs de comparaison"""
        
        if actual is None:
            return False
        
        try:
            if operator == 'EQ':
                return actual == expected
            elif operator == 'NE':
                return actual != expected
            elif operator == 'GT':
                return float(actual) > float(expected)
            elif operator == 'GTE':
                return float(actual) >= float(expected)
            elif operator == 'LT':
                return float(actual) < float(expected)
            elif operator == 'LTE':
                return float(actual) <= float(expected)
            elif operator == 'IN':
                return actual in expected if isinstance(expected, list) else False
            elif operator == 'NOT_IN':
                return actual not in expected if isinstance(expected, list) else True
            elif operator == 'CONTAINS':
                return str(expected).lower() in str(actual).lower()
            elif operator == 'BETWEEN':
                if isinstance(expected, list) and len(expected) == 2:
                    return float(expected[0]) <= float(actual) <= float(expected[1])
                return False
            else:
                return False
                
        except (ValueError, TypeError) as e:
            logger.warning(f"Erreur comparaison {actual} {operator} {expected}: {e}")
            return False
    
    def _calculate_gradual_score(self, actual: float, expected: float, operator: str) -> float:
        """Calcul score graduel pour règles numériques"""
        
        try:
            actual_f = float(actual)
            expected_f = float(expected)
            
            if operator in ['LTE', 'LT']:
                # Plus la valeur est basse, mieux c'est
                if actual_f <= expected_f:
                    return 100.0
                else:
                    # Score décroissant jusqu'à 0 à 2x la valeur attendue
                    ratio = min(2.0, actual_f / expected_f)
                    return max(0.0, 100.0 * (2.0 - ratio))
            
            elif operator in ['GTE', 'GT']:
                # Plus la valeur est haute, mieux c'est
                if actual_f >= expected_f:
                    return 100.0
                else:
                    # Score croissant à partir de 50% de la valeur attendue
                    min_threshold = expected_f * 0.5
                    if actual_f <= min_threshold:
                        return 0.0
                    ratio = (actual_f - min_threshold) / (expected_f - min_threshold)
                    return ratio * 100.0
            
            return 100.0 if self._apply_operator(actual, expected, operator) else 0.0
            
        except (ValueError, TypeError):
            return 0.0
    
    def _calculate_final_eligibility(
        self, 
        program: SocialProgram, 
        rule_results: Dict
    ) -> Dict:
        """Calcul de l'éligibilité finale et score composite"""
        
        failed_mandatory = []
        total_score = 0.0
        total_weight = 0.0
        rule_count = len(rule_results)
        
        for rule_id, result in rule_results.items():
            rule_score = result.get('score', 0.0)
            rule_weight = result.get('weight', 1.0)
            is_mandatory = result.get('is_mandatory', True)
            
            # Vérification règles obligatoires
            if is_mandatory and not result.get('passed', False):
                failed_mandatory.append(result.get('rule_name', rule_id))
            
            # Accumulation score pondéré
            total_score += rule_score * rule_weight
            total_weight += rule_weight
        
        # Score composite
        composite_score = total_score / total_weight if total_weight > 0 else 0.0
        
        # Décision finale
        is_eligible = (
            len(failed_mandatory) == 0 and  # Toutes règles obligatoires passées
            composite_score >= 60.0 and     # Score minimum
            program.is_budget_available      # Budget disponible
        )
        
        # Calcul confiance basé sur completude des données
        confidence = min(100.0, composite_score * 0.8 + rule_count * 2.0)
        
        return {
            'is_eligible': is_eligible,
            'score': round(composite_score, 2),
            'confidence': round(confidence, 2),
            'failed_mandatory': failed_mandatory,
            'total_rules_evaluated': rule_count
        }

class VulnerabilityCalculator:
    """Calculateur de score de vulnérabilité multi-dimensionnel"""
    
    def __init__(self):
        self.weights = {
            'demographic': 0.25,
            'economic': 0.35,
            'social': 0.20,
            'health': 0.15,
            'geographic': 0.05
        }
    
    def calculate_vulnerability_score(
        self, 
        person: PersonIdentity, 
        context_data: Dict = None
    ) -> VulnerabilityScore:
        """Calcul complet du score de vulnérabilité"""
        
        # Scores par dimension
        demographic_score = self._calculate_demographic_score(person)
        economic_score = self._calculate_economic_score(person, context_data)
        social_score = self._calculate_social_score(person, context_data)
        health_score = self._calculate_health_score(person, context_data)
        geographic_score = self._calculate_geographic_score(person)
        
        # Score global pondéré
        overall_score = (
            demographic_score * self.weights['demographic'] +
            economic_score * self.weights['economic'] +
            social_score * self.weights['social'] +
            health_score * self.weights['health'] +
            geographic_score * self.weights['geographic']
        )
        
        # Classification
        vulnerability_level = self._classify_vulnerability_level(overall_score)
        
        # Facteurs contributeurs
        contributing_factors = self._identify_contributing_factors({
            'demographic': demographic_score,
            'economic': economic_score,
            'social': social_score,
            'health': health_score,
            'geographic': geographic_score
        })
        
        # Mise à jour ou création
        vulnerability_score, created = VulnerabilityScore.objects.update_or_create(
            person=person,
            defaults={
                'overall_score': round(overall_score, 2),
                'demographic_score': round(demographic_score, 2),
                'economic_score': round(economic_score, 2),
                'social_score': round(social_score, 2),
                'health_score': round(health_score, 2),
                'geographic_score': round(geographic_score, 2),
                'contributing_factors': contributing_factors,
                'calculation_version': '1.0',
                'confidence_level': 85.0,  # À calculer selon completude données
                'vulnerability_level': vulnerability_level
            }
        )
        
        return vulnerability_score
    
    def _calculate_demographic_score(self, person: PersonIdentity) -> float:
        """Score basé sur facteurs démographiques"""
        
        score = 0.0
        
        # Âge (vulnérabilité aux extrêmes)
        age = self._calculate_age(person.date_of_birth)
        if age < 18 or age > 65:
            score += 30.0
        elif age < 25 or age > 55:
            score += 15.0
        
        # Genre (femmes plus vulnérables statistiquement)
        if person.gender == 'F':
            score += 10.0
        
        # Chef de famille femme
        if person.gender == 'F' and self._is_household_head(person):
            score += 20.0
        
        # Statut marital
        if getattr(person, 'marital_status', None) in ['DIVORCED', 'WIDOWED']:
            score += 15.0
        
        return min(100.0, score)
    
    def _calculate_economic_score(self, person: PersonIdentity, context_data: Dict = None) -> float:
        """Score basé sur situation économique"""
        
        score = 0.0
        
        if context_data:
            # Revenus
            monthly_income = context_data.get('monthly_income')
            if monthly_income is not None:
                # Seuil pauvreté Gabon (approximatif)
                poverty_line = 75000  # FCFA/mois
                
                if monthly_income <= poverty_line:
                    score += 60.0
                elif monthly_income <= poverty_line * 1.5:
                    score += 40.0
                elif monthly_income <= poverty_line * 2:
                    score += 20.0
            
            # Statut emploi
            employment_status = context_data.get('employment_status')
            if employment_status in ['UNEMPLOYED', 'INFORMAL']:
                score += 30.0
            elif employment_status == 'PART_TIME':
                score += 15.0
            
            # Type de logement
            housing_type = context_data.get('housing_type')
            if housing_type in ['PRECARIOUS', 'HOMELESS']:
                score += 40.0
            elif housing_type == 'RENTAL':
                score += 10.0
        
        # Nombre de dépendants économiques
        dependents = self._get_dependents_count(person)
        if dependents > 3:
            score += 25.0
        elif dependents > 0:
            score += 10.0
        
        return min(100.0, score)
    
    def _calculate_social_score(self, person: PersonIdentity, context_data: Dict = None) -> float:
        """Score basé sur facteurs sociaux"""
        
        score = 0.0
        
        # Isolement social (peu de liens familiaux)
        family_size = self._get_family_size(person)
        if family_size <= 1:
            score += 30.0
        elif family_size <= 2:
            score += 15.0
        
        # Niveau d'éducation
        if context_data and context_data.get('education_level'):
            education_level = context_data['education_level']
            if education_level in ['NONE', 'PRIMARY_INCOMPLETE']:
                score += 25.0
            elif education_level == 'PRIMARY_COMPLETE':
                score += 10.0
        
        # Handicap ou besoins spéciaux (inféré des services utilisés)
        # Logique à adapter selon données disponibles
        
        return min(100.0, score)
    
    def _calculate_health_score(self, person: PersonIdentity, context_data: Dict = None) -> float:
        """Score basé sur état de santé"""
        
        score = 0.0
        
        if context_data:
            health_status = context_data.get('health_status')
            if health_status == 'POOR':
                score += 50.0
            elif health_status == 'FAIR':
                score += 25.0
            
            # Handicap déclaré
            if context_data.get('has_disability'):
                score += 30.0
            
            # Maladie chronique
            if context_data.get('chronic_illness'):
                score += 20.0
        
        # Âge et santé (corrélation)
        age = self._calculate_age(person.date_of_birth)
        if age > 70:
            score += 15.0
        elif age > 60:
            score += 10.0
        
        return min(100.0, score)
    
    def _calculate_geographic_score(self, person: PersonIdentity) -> float:
        """Score basé sur localisation géographique"""
        
        score = 0.0
        
        # Zone rurale vs urbaine
        division = person.administrative_division
        if division:
            # Logique à adapter selon classification administrative gabonaise
            rural_divisions = ['RURAL_1', 'RURAL_2']  # À définir
            if division in rural_divisions:
                score += 30.0
        
        # Éloignement des services (si coordonnées GPS disponibles)
        if person.gps_coordinates:
            # Distance aux services essentiels
            # Implémentation selon données géospatiales disponibles
            pass
        
        return min(100.0, score)
    
    def _classify_vulnerability_level(self, overall_score: float) -> str:
        """Classification du niveau de vulnérabilité"""
        
        if overall_score >= 80:
            return 'CRITICAL'
        elif overall_score >= 60:
            return 'HIGH'
        elif overall_score >= 40:
            return 'MODERATE'
        else:
            return 'LOW'
    
    def _identify_contributing_factors(self, dimension_scores: Dict) -> List[Dict]:
        """Identification des facteurs contributeurs principaux"""
        
        factors = []
        
        for dimension, score in dimension_scores.items():
            if score >= 50.0:  # Seuil significatif
                factors.append({
                    'dimension': dimension,
                    'score': score,
                    'weight': self.weights.get(dimension, 0.0),
                    'contribution': score * self.weights.get(dimension, 0.0)
                })
        
        # Tri par contribution décroissante
        factors.sort(key=lambda x: x['contribution'], reverse=True)
        
        return factors

# Service de ciblage géographique
class GeographicTargetingService:
    """Service de ciblage et optimisation géographique"""
    
    def __init__(self):
        self.redis_client = cache  # Utilisation du cache Django
    
    def identify_priority_zones(
        self, 
        program: SocialProgram, 
        max_zones: int = 20
    ) -> List[Dict]:
        """Identification des zones prioritaires pour un programme"""
        
        cache_key = f"priority_zones:{program.id}:{max_zones}"
        cached_zones = self.redis_client.get(cache_key)
        if cached_zones:
            return cached_zones
        
        from django.db import connection
        
        # Requête optimisée avec agrégations spatiales
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    p.administrative_division,
                    COUNT(*) as potential_beneficiaries,
                    AVG(vs.overall_score) as avg_vulnerability_score,
                    ST_Centroid(ST_Union(p.gps_coordinates)) as zone_center,
                    COUNT(*) * AVG(vs.overall_score) as priority_score
                FROM identity_persons p
                LEFT JOIN eligibility_vulnerability_scores vs ON vs.person_id = p.id
                WHERE p.verification_status = 'VERIFIED'
                    AND vs.overall_score >= %s
                GROUP BY p.administrative_division
                HAVING COUNT(*) >= %s
                ORDER BY priority_score DESC
                LIMIT %s
            """, [
                60.0,  # Score vulnérabilité minimum
                50,    # Nombre minimum bénéficiaires potentiels
                max_zones
            ])
            
            zones = []
            for row in cursor.fetchall():
                zones.append({
                    'division': row[0],
                    'potential_beneficiaries': row[1],
                    'avg_vulnerability_score': float(row[2]) if row[2] else 0.0,
                    'zone_center': {
                        'lat': row[3].y if row[3] else None,
                        'lon': row[3].x if row[3] else None
                    },
                    'priority_score': float(row[4]) if row[4] else 0.0
                })
        
        # Mise en cache pour 1 heure
        self.redis_client.set(cache_key, zones, 3600)
        
        return zones
    
    def optimize_resource_allocation(
        self, 
        program: SocialProgram, 
        zones: List[Dict], 
        total_budget: Decimal
    ) -> Dict:
        """Optimisation de l'allocation budgétaire par zone"""
        
        # Algorithme d'optimisation simplifié
        # (à remplacer par optimisation plus sophistiquée si nécessaire)
        
        total_priority_score = sum(zone['priority_score'] for zone in zones)
        allocation_results = []
        
        for zone in zones:
            # Allocation proportionnelle au score de priorité
            zone_allocation = (
                total_budget * Decimal(zone['priority_score']) / 
                Decimal(total_priority_score)
            )
            
            # Nombre de bénéficiaires selon montant d'aide
            estimated_beneficiaries = int(zone_allocation / program.benefit_amount) if program.benefit_amount else 0
            
            allocation_results.append({
                'zone': zone['division'],
                'allocated_budget': float(zone_allocation),
                'estimated_beneficiaries': min(estimated_beneficiaries, zone['potential_beneficiaries']),
                'coverage_rate': min(1.0, estimated_beneficiaries / zone['potential_beneficiaries']) if zone['potential_beneficiaries'] else 0.0
            })
        
        return {
            'allocations': allocation_results,
            'total_allocated': float(total_budget),
            'total_estimated_beneficiaries': sum(a['estimated_beneficiaries'] for a in allocation_results),
            'optimization_method': 'proportional_priority'
        }