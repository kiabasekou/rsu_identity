# apps/eligibility/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg
from .models import SocialProgram, EligibilityRule, EligibilityEvaluation, VulnerabilityScore
from .serializers import (
    SocialProgramSerializer, EligibilityRuleSerializer, 
    EligibilityEvaluationSerializer, VulnerabilityScoreSerializer
)
from .services import EligibilityEngine, VulnerabilityCalculator, GeographicTargetingService
from apps.identity.models import PersonIdentity
import logging

logger = logging.getLogger(__name__)

class SocialProgramViewSet(viewsets.ModelViewSet):
    """ViewSet pour gestion des programmes sociaux"""
    
    queryset = SocialProgram.objects.all()
    serializer_class = SocialProgramSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['program_type', 'is_active']
    
    @action(detail=True, methods=['post'])
    def evaluate_eligibility(self, request, pk=None):
        """Évaluation d'éligibilité pour une personne"""
        
        program = self.get_object()
        person_id = request.data.get('person_id')
        context_data = request.data.get('context_data', {})
        
        try:
            person = PersonIdentity.objects.get(id=person_id)
            
            eligibility_engine = EligibilityEngine()
            evaluation = eligibility_engine.evaluate_person_eligibility(
                person=person,
                program=program,
                context_data=context_data
            )
            
            serializer = EligibilityEvaluationSerializer(evaluation)
            return Response(serializer.data)
            
        except PersonIdentity.DoesNotExist:
            return Response(
                {'error': 'Personne non trouvée'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erreur évaluation éligibilité: {e}")
            return Response(
                {'error': 'Erreur lors de l\'évaluation'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def priority_zones(self, request, pk=None):
        """Zones prioritaires pour le programme"""
        
        program = self.get_object()
        max_zones = int(request.query_params.get('max_zones', 20))
        
        try:
            targeting_service = GeographicTargetingService()
            zones = targeting_service.identify_priority_zones(program, max_zones)
            
            return Response({
                'program_id': program.id,
                'program_name': program.name,
                'priority_zones': zones,
                'total_zones': len(zones)
            })
            
        except Exception as e:
            logger.error(f"Erreur calcul zones prioritaires: {e}")
            return Response(
                {'error': 'Erreur calcul zones prioritaires'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def optimize_allocation(self, request, pk=None):
        """Optimisation allocation budgétaire"""
        
        program = self.get_object()
        zones_data = request.data.get('zones', [])
        total_budget = request.data.get('total_budget', program.total_budget)
        
        try:
            targeting_service = GeographicTargetingService()
            optimization = targeting_service.optimize_resource_allocation(
                program=program,
                zones=zones_data,
                total_budget=total_budget
            )
            
            return Response(optimization)
            
        except Exception as e:
            logger.error(f"Erreur optimisation allocation: {e}")
            return Response(
                {'error': 'Erreur optimisation allocation'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VulnerabilityScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour consultation des scores de vulnérabilité"""
    
    queryset = VulnerabilityScore.objects.select_related('person')
    serializer_class = VulnerabilityScoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['vulnerability_level']
    
    @action(detail=False, methods=['post'])
    def calculate_score(self, request):
        """Calcul de score de vulnérabilité pour une personne"""
        
        person_id = request.data.get('person_id')
        context_data = request.data.get('context_data', {})
        
        try:
            person = PersonIdentity.objects.get(id=person_id)
            
            vulnerability_calculator = VulnerabilityCalculator()
            score = vulnerability_calculator.calculate_vulnerability_score(
                person=person,
                context_data=context_data
            )
            
            serializer = self.get_serializer(score)
            return Response(serializer.data)
            
        except PersonIdentity.DoesNotExist:
            return Response(
                {'error': 'Personne non trouvée'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erreur calcul vulnérabilité: {e}")
            return Response(
                {'error': 'Erreur calcul vulnérabilité'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques globales des scores de vulnérabilité"""
        
        stats = VulnerabilityScore.objects.aggregate(
            total_scores=Count('id'),
            avg_overall_score=Avg('overall_score'),
            critical_count=Count('id', filter=Q(vulnerability_level='CRITICAL')),
            high_count=Count('id', filter=Q(vulnerability_level='HIGH')),
            moderate_count=Count('id', filter=Q(vulnerability_level='MODERATE')),
            low_count=Count('id', filter=Q(vulnerability_level='LOW'))
        )
        
        return Response(stats)

class EligibilityEvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour consultation des évaluations d'éligibilité"""
    
    queryset = EligibilityEvaluation.objects.select_related('person', 'program')
    serializer_class = EligibilityEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_eligible', 'program']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtres par query parameters
        person_id = self.request.query_params.get('person_id')
        if person_id:
            queryset = queryset.filter(person_id=person_id)
        
        min_score = self.request.query_params.get('min_eligibility_score')
        if min_score:
            queryset = queryset.filter(eligibility_score__gte=min_score)
        
        return queryset.order_by('-evaluated_at')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Résumé des évaluations d'éligibilité"""
        
        summary_stats = self.get_queryset().aggregate(
            total_evaluations=Count('id'),
            eligible_count=Count('id', filter=Q(is_eligible=True)),
            avg_score=Avg('eligibility_score'),
            avg_confidence=Avg('confidence_level')
        )
        
        # Ajout du taux d'éligibilité
        total = summary_stats['total_evaluations']
        eligible = summary_stats['eligible_count']
        summary_stats['eligibility_rate'] = (eligible / total * 100) if total > 0 else 0
        
        return Response(summary_stats)