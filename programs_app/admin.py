# admin.py - Interface d'administration

from django.contrib import admin
from .models import SocialProgram, Beneficiary, Payment, DigitalVoucher

@admin.register(SocialProgram)
class SocialProgramAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'program_type', 'status', 'current_beneficiaries', 'max_beneficiaries', 'start_date']
    list_filter = ['program_type', 'status', 'is_nationwide', 'responsible_ministry']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'is_active', 'is_accepting_registrations', 'budget_remaining']
    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'name', 'description', 'program_type', 'status')
        }),
        ('Configuration financière', {
            'fields': ('budget_total', 'budget_allocated', 'budget_remaining', 'amount_per_beneficiary', 'payment_frequency')
        }),
        ('Période d\'exécution', {
            'fields': ('start_date', 'end_date', 'registration_start', 'registration_end')
        }),
        ('Ciblage géographique', {
            'fields': ('is_nationwide', 'target_provinces', 'target_cities')
        }),
        ('Critères d\'éligibilité', {
            'fields': ('min_age', 'max_age', 'target_gender', 'max_income_threshold', 'required_documents')
        }),
        ('Gestion', {
            'fields': ('max_beneficiaries', 'current_beneficiaries', 'manager', 'responsible_ministry', 'contact_person', 'contact_phone', 'contact_email')
        }),
        ('Métadonnées', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ['beneficiary_number', 'person', 'program', 'status', 'registration_date', 'eligibility_score']
    list_filter = ['status', 'program', 'verification_status', 'registration_date']
    search_fields = ['beneficiary_number', 'person__first_name', 'person__last_name', 'person__national_id']
    readonly_fields = ['id', 'beneficiary_number', 'registration_date', 'is_active', 'days_in_program']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_reference', 'beneficiary', 'amount', 'status', 'payment_method', 'initiated_date']
    list_filter = ['status', 'payment_method', 'initiated_date']
    search_fields = ['payment_reference', 'recipient_name', 'external_transaction_id']
    readonly_fields = ['id', 'payment_reference', 'initiated_date']

@admin.register(DigitalVoucher)
class DigitalVoucherAdmin(admin.ModelAdmin):
    list_display = ['voucher_code', 'beneficiary', 'face_value', 'remaining_value', 'status', 'expiry_date']
    list_filter = ['status', 'issue_date', 'expiry_date']
    search_fields = ['voucher_code', 'beneficiary__beneficiary_number']
    readonly_fields = ['id', 'voucher_code', 'qr_code', 'issue_date', 'is_usable', 'usage_percentage']


