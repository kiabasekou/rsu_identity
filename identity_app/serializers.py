# serializers.py - API Serializers pour Identity App
from rest_framework import serializers
from .models import PersonIdentity, DeduplicationCandidate, FamilyRelationship

class PersonIdentitySerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    age = serializers.ReadOnlyField()
    
    class Meta:
        model = PersonIdentity
        fields = [
            'id', 'first_name', 'last_name', 'middle_name', 'full_name',
            'birth_date', 'age', 'birth_place', 'gender', 'marital_status',
            'national_id', 'passport_number', 'birth_certificate_number',
            'phone_number', 'email',
            'address_line1', 'address_line2', 'city', 'province', 'postal_code',
            'latitude', 'longitude', 'location_accuracy',
            'occupation', 'education_level', 'monthly_income', 'household_size',
            'is_validated', 'validated_at', 'rbpp_synchronized', 'rbpp_last_sync',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'full_name', 'age', 'created_at', 'updated_at']

class DeduplicationCandidateSerializer(serializers.ModelSerializer):
    person1_name = serializers.CharField(source='person1.full_name', read_only=True)
    person2_name = serializers.CharField(source='person2.full_name', read_only=True)
    
    class Meta:
        model = DeduplicationCandidate
        fields = [
            'id', 'person1', 'person2', 'person1_name', 'person2_name',
            'similarity_score', 'match_type', 'matching_fields', 'conflicting_fields',
            'confidence_factors', 'status', 'resolved_at', 'resolution_notes',
            'detected_at', 'algorithm_version'
        ]
        read_only_fields = ['id', 'detected_at', 'algorithm_version']

class FamilyRelationshipSerializer(serializers.ModelSerializer):
    person1_name = serializers.CharField(source='person1.full_name', read_only=True)
    person2_name = serializers.CharField(source='person2.full_name', read_only=True)
    relationship_display = serializers.CharField(source='get_relationship_type_display', read_only=True)
    
    class Meta:
        model = FamilyRelationship
        fields = [
            'id', 'person1', 'person2', 'person1_name', 'person2_name',
            'relationship_type', 'relationship_display', 'is_verified',
            'verified_at', 'supporting_documents', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']