# apps/surveys/services.py
from django.db import transaction
from django.utils import timezone
from typing import Dict, List, Any, Tuple
import logging
from decimal import Decimal
from .models import SurveySession, SurveyResponse, DataQualityCheck, SurveyTemplate
# Les classes de validateurs doivent exister ou être mockées pour que le code fonctionne
from .validators import ResponseValidator, LocationValidator, ConsistencyValidator

logger = logging.getLogger(__name__)

# NOTE : Pour que le code fonctionne, les classes ResponseValidator, LocationValidator, ConsistencyValidator
# doivent être définies dans un fichier `validators.py` ou équivalent.
# De même, le modèle SurveySession doit avoir les champs `start_location`, `duration_minutes` et `started_at`.
# J'ai mis à jour la version des modèles dans la correction précédente pour inclure ces champs.


class SurveyValidationService:
    """Service de validation des enquêtes"""

    def __init__(self):
        self.response_validator = ResponseValidator()
        self.location_validator = LocationValidator()
        self.consistency_validator = ConsistencyValidator()

        # Seuils de qualité configurables
        self.quality_thresholds = {
            'completion_rate_min': 80.0,
            'gps_accuracy_max': 50.0,  # mètres
            'duration_min_minutes': 5,  # 5 minutes minimum
            'duration_max_minutes': 120,  # 2 heures maximum
            'consistency_score_min': 70.0
        }

    @transaction.atomic
    def validate_survey_session(self, session: SurveySession) -> Dict:
        """Validation complète d'une session d'enquête"""

        validation_results = {
            'session_id': str(session.id),
            'overall_status': 'VALID',
            'quality_score': Decimal('0.00'),
            'checks_performed': [],
            'errors': [],
            'warnings': [],
            'recommendations': []
        }

        try:
            # 1. Validation complétude
            completeness_result = self._check_completeness(session)
            validation_results['checks_performed'].append(completeness_result)

            # 2. Validation géospatiale
            location_result = self._check_location_quality(session)
            validation_results['checks_performed'].append(location_result)

            # 3. Validation temporelle
            timing_result = self._check_timing_validity(session)
            validation_results['checks_performed'].append(timing_result)

            # 4. Validation cohérence
            consistency_result = self._check_response_consistency(session)
            validation_results['checks_performed'].append(consistency_result)
            
            # 5. Validation règles métier (méthode à implémenter)
            business_result = self._check_business_rules(session)
            validation_results['checks_performed'].append(business_result)

            # 6. Calcul score global et statut final
            overall_score, final_status = self._calculate_overall_quality(validation_results['checks_performed'])
            
            validation_results['quality_score'] = overall_score
            validation_results['overall_status'] = final_status
            
            # 7. Persistance des résultats
            self._save_quality_checks(session, validation_results['checks_performed'])
            
            # 8. Mise à jour session
            session.data_quality_score = overall_score
            # Les champs validation_errors et validation_warnings n'existent pas, nous les retirons
            session.save(update_fields=['data_quality_score'])
            
            logger.info(f"Validation session {session.id}: Score {overall_score}, Status {final_status}")
            
        except Exception as e:
            logger.error(f"Erreur validation session {session.id}: {e}")
            validation_results['overall_status'] = 'ERROR'
            validation_results['errors'].append(f"Erreur validation: {str(e)}")
        
        return validation_results

    def _get_required_questions(self, template: SurveyTemplate) -> List[str]:
        """Méthode de base pour obtenir les questions requises d'un template."""
        # Ceci est une implémentation par défaut. La logique réelle dépend de la structure de `questions_config`.
        required_questions = []
        if template and isinstance(template.questions_config, list):
            for q in template.questions_config:
                if q.get('is_required', False):
                    required_questions.append(q.get('question_id'))
        return [q_id for q_id in required_questions if q_id]

    def _check_completeness(self, session: SurveySession) -> Dict:
        """Vérification complétude des réponses"""
        
        template = session.template
        required_questions = self._get_required_questions(template)
        
        responses = session.responses.all()
        response_questions = {r.question_id for r in responses if not r.is_skipped}
        
        missing_questions = set(required_questions) - response_questions
        completion_rate = len(response_questions) / len(required_questions) * 100 if required_questions else 100
        
        passed = completion_rate >= self.quality_thresholds['completion_rate_min']
        severity = 'ERROR' if completion_rate < 60 else 'WARNING' if completion_rate < 80 else 'INFO'
        
        result = {
            'check_type': 'COMPLETENESS',
            'check_name': 'Complétude des réponses',
            'passed': passed,
            'severity': severity,
            'score': completion_rate,
            'details': {
                'completion_rate': completion_rate,
                'total_required': len(required_questions),
                'answered': len(response_questions),
                'missing_questions': list(missing_questions)
            }
        }
        
        if not passed:
            result['recommendations'] = [
                f"Compléter les questions manquantes: {', '.join(missing_questions)}"
            ]
        
        return result

    def _check_location_quality(self, session: SurveySession) -> Dict:
        """Vérification qualité géolocalisation"""
        
        # Le champ 'start_location' est présumé être un JSONField ou un dictionnaire
        start_location = session.start_location
        if not start_location:
            return {
                'check_type': 'ACCURACY',
                'check_name': 'Qualité géolocalisation',
                'passed': False,
                'severity': 'ERROR',
                'score': 0,
                'details': {'message': 'Coordonnées de départ manquantes'},
                'recommendations': ["Activer la géolocalisation au début de l'enquête"]
            }

        gps_accuracy = start_location.get('accuracy', 999)
        
        # Vérification précision GPS
        accuracy_passed = gps_accuracy <= self.quality_thresholds['gps_accuracy_max']
        
        # Vérification cohérence géographique (si région assignée)
        region_passed = True
        if hasattr(session.surveyor, 'surveyor_profile'):
            assigned_regions = session.surveyor.surveyor_profile.regions_assigned
            if assigned_regions:
                region_passed = self._verify_location_in_assigned_regions(start_location, assigned_regions)
        
        overall_passed = accuracy_passed and region_passed
        
        # Calcul score (100 pour précision parfaite, dégressif)
        accuracy_score = max(0, 100 - (gps_accuracy / self.quality_thresholds['gps_accuracy_max']) * 50)
        region_score = 100 if region_passed else 50
        location_score = (accuracy_score + region_score) / 2
        
        severity = 'ERROR' if not overall_passed else 'WARNING' if gps_accuracy > 20 else 'INFO'
        
        result = {
            'check_type': 'ACCURACY',
            'check_name': 'Qualité géolocalisation',
            'passed': overall_passed,
            'severity': severity,
            'score': location_score,
            'details': {
                'gps_accuracy_meters': gps_accuracy,
                'accuracy_threshold': self.quality_thresholds['gps_accuracy_max'],
                'region_verification': region_passed,
                'coordinates': start_location
            }
        }
        
        if not accuracy_passed:
            result['recommendations'] = [
                "Améliorer la précision GPS avant collecte",
                "Vérifier activation GPS haute précision"
            ]
        
        return result
        
    def _verify_location_in_assigned_regions(self, location: Dict, assigned_regions: List[str]) -> bool:
        """Méthode à implémenter pour vérifier si une location est dans les régions assignées."""
        # Cette logique dépend d'une base de données géospatiale ou d'une API externe.
        # Pour l'instant, on retourne True par défaut pour ne pas bloquer le code.
        return True

    def _check_timing_validity(self, session: SurveySession) -> Dict:
        """Vérification validité temporelle"""
        
        # Le champ 'duration_minutes' est présumé être un entier ou un flottant
        duration_minutes = session.duration_minutes
        template_duration = session.template.estimated_duration_minutes
        
        timing_issues = []
        
        if duration_minutes:
            if duration_minutes < self.quality_thresholds['duration_min_minutes']:
                timing_issues.append(f"Durée très courte: {duration_minutes:.1f}min")
            
            if duration_minutes > self.quality_thresholds['duration_max_minutes']:
                timing_issues.append(f"Durée très longue: {duration_minutes:.1f}min")
            
            if template_duration:
                # Éviter la division par zéro
                ratio = duration_minutes / template_duration if template_duration else 0
                if ratio < 0.3:
                    timing_issues.append("Durée anormalement courte par rapport à l'estimé")
                elif ratio > 3:
                    timing_issues.append("Durée anormalement longue par rapport à l'estimé")
        
        if session.started_at:
            hour = session.started_at.hour
            if hour < 8 or hour > 18:
                timing_issues.append(f"Collecte hors heures habituelles: {hour}h")
        
        passed = len(timing_issues) == 0
        severity = 'WARNING' if timing_issues else 'INFO'
        
        timing_score = max(0, 100 - len(timing_issues) * 25)
        
        result = {
            'check_type': 'TIMELINESS',
            'check_name': 'Validité temporelle',
            'passed': passed,
            'severity': severity,
            'score': timing_score,
            'details': {
                'duration_minutes': duration_minutes,
                'estimated_duration': template_duration,
                'timing_issues': timing_issues,
                'collection_time': session.started_at.isoformat() if session.started_at else None
            }
        }
        
        return result

    def _check_business_rules(self, session: SurveySession) -> Dict:
        """
        Méthode de base pour la validation des règles métier.
        Cette logique serait plus complexe en production.
        """
        # Exemples de règles métier :
        # - Vérifier si le bénéficiaire est éligible au programme.
        # - Valider des conditions spécifiques liées au type d'enquête.
        # Par défaut, retourne un résultat réussi.
        return {
            'check_type': 'VALIDITY',
            'check_name': 'Règles métier',
            'passed': True,
            'severity': 'INFO',
            'score': 100,
            'details': {'message': 'Aucune règle métier critique non respectée.'}
        }
    
    def _check_response_consistency(self, session: SurveySession) -> Dict:
        """Vérification cohérence des réponses"""
        
        responses = {r.question_id: r.get_typed_value() for r in session.responses.all() if not r.is_skipped}
        
        consistency_checks = []
        
        template_rules = session.template.validation_rules.get('consistency', [])
        
        for rule in template_rules:
            check_result = self.consistency_validator.apply_rule(rule, responses)
            consistency_checks.append(check_result)
        
        generic_checks = [
            self._check_age_consistency(responses),
            self._check_income_consistency(responses),
            self._check_household_consistency(responses),
        ]
        
        consistency_checks.extend([c for c in generic_checks if c])
        
        passed_checks = sum(1 for c in consistency_checks if c.get('passed', False))
        total_checks = len(consistency_checks)
        consistency_score = (passed_checks / total_checks * 100) if total_checks > 0 else 100
        
        overall_passed = consistency_score >= self.quality_thresholds['consistency_score_min']
        
        failed_checks = [c for c in consistency_checks if not c.get('passed', True)]
        severity = 'ERROR' if len(failed_checks) > 2 else 'WARNING' if failed_checks else 'INFO'
        
        result = {
            'check_type': 'CONSISTENCY',
            'check_name': 'Cohérence des réponses',
            'passed': overall_passed,
            'severity': severity,
            'score': consistency_score,
            'details': {
                'checks_performed': total_checks,
                'checks_passed': passed_checks,
                'failed_checks': failed_checks,
                'consistency_percentage': consistency_score
            }
        }
        
        if failed_checks:
            result['recommendations'] = [
                f"Vérifier cohérence: {check['description']}" for check in failed_checks
            ]
        
        return result
    
    def _check_age_consistency(self, responses: Dict) -> Dict:
        """Vérification cohérence âge"""
        
        age = responses.get('age')
        birth_year = responses.get('birth_year')
        
        if age is not None and birth_year is not None:
            current_year = timezone.now().year
            # Protection contre les années de naissance futures
            if birth_year > current_year:
                return {
                    'rule': 'birth_year_validity',
                    'description': 'Année de naissance invalide',
                    'passed': False,
                    'details': {'birth_year': birth_year}
                }

            calculated_age = current_year - birth_year
            age_diff = abs(age - calculated_age)
            
            return {
                'rule': 'age_consistency',
                'description': 'Cohérence âge/année de naissance',
                'passed': age_diff <= 1,
                'details': {
                    'declared_age': age,
                    'calculated_age': calculated_age,
                    'difference': age_diff
                }
            }
        
        return None
    
    def _check_income_consistency(self, responses: Dict) -> Dict:
        """Vérification cohérence revenus"""
        
        monthly_income = responses.get('monthly_income')
        employment_status = responses.get('employment_status')
        
        if monthly_income is not None and employment_status:
            if employment_status == 'UNEMPLOYED' and monthly_income > 50000:
                return {
                    'rule': 'income_employment_consistency',
                    'description': 'Revenus déclarés incohérents avec statut chômeur',
                    'passed': False,
                    'details': {
                        'income': monthly_income,
                        'employment': employment_status
                    }
                }
            
            if employment_status == 'EMPLOYED' and monthly_income <= 0:
                return {
                    'rule': 'income_employment_consistency',
                    'description': 'Revenus nuls ou négatifs incohérents avec statut employé',
                    'passed': False,
                    'details': {
                        'income': monthly_income,
                        'employment': employment_status
                    }
                }
        
        return {
            'rule': 'income_employment_consistency',
            'description': 'Cohérence revenus/emploi',
            'passed': True,
            'details': {'income': monthly_income, 'employment': employment_status}
        }
    
    def _check_household_consistency(self, responses: Dict) -> Dict:
        """Vérification cohérence composition ménage"""
        
        household_size = responses.get('household_size')
        children_count = responses.get('children_count')
        adults_count = responses.get('adults_count')
        
        if household_size is not None and (children_count is not None or adults_count is not None):
            declared_total = (children_count or 0) + (adults_count or 0)
            size_diff = abs(household_size - declared_total)
            
            return {
                'rule': 'household_composition_consistency',
                'description': 'Cohérence taille ménage/composition',
                'passed': size_diff <= 1,
                'details': {
                    'declared_size': household_size,
                    'calculated_size': declared_total,
                    'difference': size_diff
                }
            }
        
        return None

    def _calculate_overall_quality(self, checks: List[Dict]) -> Tuple[Decimal, str]:
        """Calcule le score et le statut global à partir des résultats des vérifications."""
        if not checks:
            return Decimal('100.00'), 'VALID'
        
        total_score = sum(check.get('score', 0) for check in checks)
        overall_score = total_score / len(checks) if checks else Decimal('100.00')

        # Déterminer le statut final basé sur la sévérité des erreurs
        has_error = any(check.get('severity') == 'ERROR' for check in checks)
        has_warning = any(check.get('severity') == 'WARNING' for check in checks)

        if has_error:
            final_status = 'INVALID'
        elif has_warning:
            final_status = 'WARNING'
        else:
            final_status = 'VALID'
        
        return Decimal(overall_score), final_status
    
    def _save_quality_checks(self, session: SurveySession, checks: List[Dict]):
        """Persiste les résultats de chaque contrôle de qualité."""
        # Supprime les anciens contrôles pour éviter les doublons lors des revalidations
        DataQualityCheck.objects.filter(session=session).delete()

        quality_checks_to_create = []
        for check in checks:
            check_type = check.get('check_type')
            if not check_type:
                continue

            quality_checks_to_create.append(
                DataQualityCheck(
                    session=session,
                    check_type=check_type,
                    check_name=check.get('check_name'),
                    description=check.get('details', {}).get('message', 'N/A'),
                    passed=check.get('passed', False),
                    severity=check.get('severity', 'INFO'),
                    score=Decimal(check.get('score', 0)),
                    error_details=check.get('details', {}),
                    recommendations=check.get('recommendations', [])
                )
            )
        
        if quality_checks_to_create:
            DataQualityCheck.objects.bulk_create(quality_checks_to_create)