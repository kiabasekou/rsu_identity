# views.py - API ViewSets
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from .models import SocialProgram, Beneficiary, Payment, DigitalVoucher
from .serializers import SocialProgramSerializer, BeneficiarySerializer, PaymentSerializer, DigitalVoucherSerializer

class SocialProgramViewSet(viewsets.ModelViewSet):
    queryset = SocialProgram.objects.all()
    serializer_class = SocialProgramSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['program_type', 'status', 'is_nationwide', 'target_gender']
    search_fields = ['name', 'code', 'description', 'responsible_ministry']
    ordering_fields = ['name', 'start_date', 'created_at', 'current_beneficiaries']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, manager=self.request.user)

    @action(detail=False, methods=['get'])
    def active_programs(self, request):
        """Programmes actuellement actifs"""
        active = self.get_queryset().filter(status='ACTIVE')
        serializer = self.get_serializer(active, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques globales des programmes"""
        stats = self.get_queryset().aggregate(
            total_programs=Count('id'),
            active_programs=Count('id', filter=Q(status='ACTIVE')),
            total_budget=Sum('budget_total'),
            total_beneficiaries=Sum('current_beneficiaries')
        )
        return Response(stats)

class BeneficiaryViewSet(viewsets.ModelViewSet):
    queryset = Beneficiary.objects.select_related('person', 'program').all()
    serializer_class = BeneficiarySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'program', 'verification_status']
    search_fields = ['beneficiary_number', 'person__first_name', 'person__last_name', 'person__national_id']
    ordering_fields = ['registration_date', 'approval_date', 'eligibility_score']
    ordering = ['-registration_date']

    def perform_create(self, serializer):
        # Générer automatiquement le numéro de bénéficiaire
        program = serializer.validated_data['program']
        last_number = Beneficiary.objects.filter(program=program).count()
        beneficiary_number = f"{program.code}-BEN-{last_number + 1:06d}"
        serializer.save(
            created_by=self.request.user,
            beneficiary_number=beneficiary_number
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuver un bénéficiaire"""
        beneficiary = self.get_object()
        beneficiary.status = 'APPROVED'
        beneficiary.approved_by = request.user
        beneficiary.save()
        return Response({'status': 'Beneficiary approved'})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activer un bénéficiaire"""
        beneficiary = self.get_object()
        beneficiary.status = 'ACTIVE'
        beneficiary.start_date = request.data.get('start_date')
        beneficiary.save()
        return Response({'status': 'Beneficiary activated'})

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('beneficiary', 'program').all()
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'program']
    search_fields = ['payment_reference', 'recipient_name', 'beneficiary__beneficiary_number']
    ordering_fields = ['initiated_date', 'amount', 'completed_date']
    ordering = ['-initiated_date']

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Traiter un paiement"""
        payment = self.get_object()
        payment.status = 'PROCESSING'
        payment.save()
        # Ici, intégration avec le système de paiement
        return Response({'status': 'Payment processing started'})

    @action(detail=False, methods=['get'])
    def pending_payments(self, request):
        """Paiements en attente"""
        pending = self.get_queryset().filter(status='PENDING')
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

class DigitalVoucherViewSet(viewsets.ModelViewSet):
    queryset = DigitalVoucher.objects.select_related('beneficiary', 'program').all()
    serializer_class = DigitalVoucherSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'program']
    search_fields = ['voucher_code', 'beneficiary__beneficiary_number']
    ordering_fields = ['issue_date', 'expiry_date', 'face_value']
    ordering = ['-issue_date']

    @action(detail=True, methods=['post'])
    def use_voucher(self, request, pk=None):
        """Utiliser un bon numérique"""
        voucher = self.get_object()
        amount = request.data.get('amount', 0)
        
        if voucher.is_usable and amount <= voucher.remaining_value:
            voucher.remaining_value -= amount
            voucher.usage_count += 1
            voucher.last_use_date = timezone.now()
            if voucher.remaining_value == 0:
                voucher.status = 'USED'
            voucher.save()
            return Response({'status': 'Voucher used successfully', 'remaining': voucher.remaining_value})
        else:
            return Response({'error': 'Voucher cannot be used'}, status=status.HTTP_400_BAD_REQUEST)
