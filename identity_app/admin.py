# 6. admin.py - Interface d'administration

from django.contrib import admin
from .models import PersonIdentity, DeduplicationCandidate, FamilyRelationship

@admin.register(PersonIdentity)
class PersonIdentityAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'national_id', 'phone_number', 'city', 'is_validated', 'created_at']
    list_filter = ['gender', 'marital_status', 'province', 'is_validated', 'rbpp_synchronized']
    search_fields = ['first_name', 'last_name', 'national_id', 'phone_number']
    readonly_fields = ['id', 'created_at', 'updated_at', 'age']
    fieldsets = (
        ('Informations personnelles', {
            'fields': ('first_name', 'last_name', 'middle_name', 'birth_date', 'birth_place', 'gender', 'marital_status')
        }),
        ('Documents', {
            'fields': ('national_id', 'passport_number', 'birth_certificate_number')
        }),
        ('Contact', {
            'fields': ('phone_number', 'email')
        }),
        ('Adresse', {
            'fields': ('address_line1', 'address_line2', 'city', 'province', 'postal_code', 'latitude', 'longitude')
        }),
        ('Socio-économique', {
            'fields': ('occupation', 'education_level', 'monthly_income', 'household_size')
        }),
        ('Validation', {
            'fields': ('is_validated', 'validated_at', 'validated_by')
        }),
        ('RBPP', {
            'fields': ('rbpp_synchronized', 'rbpp_last_sync', 'rbpp_data'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(DeduplicationCandidate)
class DeduplicationCandidateAdmin(admin.ModelAdmin):
    list_display = ['person1', 'person2', 'similarity_score', 'match_type', 'status', 'detected_at']
    list_filter = ['match_type', 'status', 'detected_at']
    readonly_fields = ['id', 'detected_at', 'algorithm_version']

@admin.register(FamilyRelationship)
class FamilyRelationshipAdmin(admin.ModelAdmin):
    list_display = ['person1', 'relationship_type', 'person2', 'is_verified', 'created_at']
    list_filter = ['relationship_type', 'is_verified']
    readonly_fields = ['id', 'created_at']
