# serializers.py - API Serializers
from rest_framework import serializers
from .models import SocialProgram, Beneficiary, Payment, DigitalVoucher

class SocialProgramSerializer(serializers.ModelSerializer):
    is_active = serializers.ReadOnlyField()
    is_accepting_registrations = serializers.ReadOnlyField()
    budget_remaining = serializers.ReadOnlyField()
    capacity_remaining = serializers.ReadOnlyField()
    
    class Meta:
        model = SocialProgram
        fields = [
            'id', 'code', 'name', 'description', 'program_type', 'status',
            'budget_total', 'budget_allocated', 'budget_remaining',
            'amount_per_beneficiary', 'payment_frequency',
            'start_date', 'end_date', 'registration_start', 'registration_end',
            'target_provinces', 'target_cities', 'is_nationwide',
            'min_age', 'max_age', 'target_gender', 'max_income_threshold',
            'required_documents', 'eligibility_rules', 'additional_criteria',
            'max_beneficiaries', 'current_beneficiaries', 'capacity_remaining',
            'responsible_ministry', 'contact_person', 'contact_phone', 'contact_email',
            'is_active', 'is_accepting_registrations', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class BeneficiarySerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    program_name = serializers.CharField(source='program.name', read_only=True)
    is_active = serializers.ReadOnlyField()
    days_in_program = serializers.ReadOnlyField()
    
    class Meta:
        model = Beneficiary
        fields = [
            'id', 'beneficiary_number', 'person', 'person_name', 'program', 'program_name',
            'status', 'registration_date', 'approval_date', 'start_date', 'end_date',
            'eligibility_score', 'vulnerability_score', 'priority_ranking',
            'monthly_payment_amount', 'total_payments_received', 'last_payment_date',
            'household_visits', 'last_visit_date', 'compliance_score',
            'submitted_documents', 'missing_documents', 'verification_status',
            'notes', 'additional_data', 'is_active', 'days_in_program'
        ]
        read_only_fields = ['id', 'beneficiary_number', 'registration_date']

class PaymentSerializer(serializers.ModelSerializer):
    beneficiary_name = serializers.CharField(source='beneficiary.person.full_name', read_only=True)
    program_name = serializers.CharField(source='program.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_reference', 'beneficiary', 'beneficiary_name', 'program', 'program_name',
            'amount', 'currency', 'payment_method', 'status',
            'payment_period_start', 'payment_period_end',
            'initiated_date', 'processed_date', 'completed_date',
            'external_transaction_id', 'payment_provider', 'fees',
            'recipient_name', 'recipient_phone', 'recipient_account',
            'failure_reason', 'notes'
        ]
        read_only_fields = ['id', 'payment_reference', 'initiated_date']

class DigitalVoucherSerializer(serializers.ModelSerializer):
    beneficiary_name = serializers.CharField(source='beneficiary.person.full_name', read_only=True)
    program_name = serializers.CharField(source='program.name', read_only=True)
    is_usable = serializers.ReadOnlyField()
    usage_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = DigitalVoucher
        fields = [
            'id', 'voucher_code', 'qr_code', 'beneficiary', 'beneficiary_name', 'program', 'program_name',
            'face_value', 'remaining_value', 'currency', 'status',
            'issue_date', 'expiry_date', 'allowed_categories', 'allowed_merchants',
            'geographic_restrictions', 'first_use_date', 'last_use_date', 'usage_count',
            'is_usable', 'usage_percentage'
        ]
        read_only_fields = ['id', 'voucher_code', 'qr_code', 'issue_date']