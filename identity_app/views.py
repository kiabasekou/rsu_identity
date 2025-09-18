# 4. views.py - API ViewSets

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models import PersonIdentity, DeduplicationCandidate, FamilyRelationship
from .serializers import PersonIdentitySerializer, DeduplicationCandidateSerializer, FamilyRelationshipSerializer

class PersonIdentityViewSet(viewsets.ModelViewSet):
    queryset = PersonIdentity.objects.all()
    serializer_class = PersonIdentitySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['gender', 'marital_status', 'city', 'province', 'is_validated', 'rbpp_synchronized']
    search_fields = ['first_name', 'last_name', 'national_id', 'phone_number']
    ordering_fields = ['first_name', 'last_name', 'birth_date', 'created_at']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def validate_identity(self, request, pk=None):
        """Valider une identité"""
        person = self.get_object()
        person.is_validated = True
        person.validated_by = request.user
        person.save()
        return Response({'status': 'Identity validated'})

    @action(detail=False, methods=['get'])
    def search_similar(self, request):
        """Rechercher des identités similaires"""
        first_name = request.query_params.get('first_name', '')
        last_name = request.query_params.get('last_name', '')
        birth_date = request.query_params.get('birth_date', '')
        
        if not (first_name and last_name):
            return Response({'error': 'first_name and last_name are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(
            Q(first_name__icontains=first_name) | Q(last_name__icontains=last_name)
        )
        
        if birth_date:
            queryset = queryset.filter(birth_date=birth_date)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class DeduplicationCandidateViewSet(viewsets.ModelViewSet):
    queryset = DeduplicationCandidate.objects.all()
    serializer_class = DeduplicationCandidateSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['match_type', 'status']
    ordering_fields = ['similarity_score', 'detected_at']
    ordering = ['-similarity_score']

    @action(detail=True, methods=['post'])
    def resolve_duplicate(self, request, pk=None):
        """Résoudre un candidat de déduplication"""
        candidate = self.get_object()
        action_type = request.data.get('action')  # 'confirm', 'reject', 'merge'
        notes = request.data.get('notes', '')
        
        if action_type == 'confirm':
            candidate.status = 'CONFIRMED'
        elif action_type == 'reject':
            candidate.status = 'REJECTED'
        elif action_type == 'merge':
            candidate.status = 'MERGED'
            # Ici, logique de fusion des identités
        else:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
        
        candidate.resolved_by = request.user
        candidate.resolution_notes = notes
        candidate.save()
        
        return Response({'status': f'Duplicate {action_type}ed'})

class FamilyRelationshipViewSet(viewsets.ModelViewSet):
    queryset = FamilyRelationship.objects.all()
    serializer_class = FamilyRelationshipSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['relationship_type', 'is_verified']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def verify_relationship(self, request, pk=None):
        """Vérifier une relation familiale"""
        relationship = self.get_object()
        relationship.is_verified = True
        relationship.verified_by = request.user
        relationship.save()
        return Response({'status': 'Relationship verified'})

    @action(detail=False, methods=['get'])
    def family_tree(self, request):
        """Obtenir l'arbre familial d'une personne"""
        person_id = request.query_params.get('person_id')
        if not person_id:
            return Response({'error': 'person_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        relationships = self.get_queryset().filter(
            Q(person1_id=person_id) | Q(person2_id=person_id)
        )
        
        serializer = self.get_serializer(relationships, many=True)
        return Response(serializer.data)

