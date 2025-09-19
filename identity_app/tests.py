# tests.py - Tests unitaires Identity App
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from .models import PersonIdentity, DeduplicationCandidate, FamilyRelationship
from datetime import date
import json

class PersonIdentityModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
    def test_create_person_identity(self):
        """Test création d'une identité"""
        person = PersonIdentity.objects.create(
            first_name='Jean',
            last_name='Dupont',
            birth_date=date(1990, 1, 1),
            birth_place='Libreville',
            gender='M',
            marital_status='SINGLE',
            national_id='123456789012',
            phone_number='+24101234567',
            address_line1='123 Rue de la Paix',
            city='Libreville',
            province='Estuaire',
            created_by=self.user
        )
        
        self.assertEqual(person.full_name, 'Jean Dupont')
        self.assertEqual(person.age, 35)  # En 2025
        self.assertTrue(str(person.id))  # UUID generated

    def test_person_validation(self):
        """Test contraintes de validation"""
        with self.assertRaises(Exception):
            # CNI doit être 12 chiffres
            PersonIdentity.objects.create(
                first_name='Test',
                last_name='User',
                birth_date=date(1990, 1, 1),
                birth_place='Test',
                gender='M',
                national_id='123',  # Trop court
                phone_number='+24101234567',
                address_line1='Test',
                city='Test',
                province='Test',
                created_by=self.user
            )

class PersonIdentityAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testapi', password='testpass')
        self.client.force_authenticate(user=self.user)
        
    def test_create_person_via_api(self):
        """Test création personne via API"""
        data = {
            'first_name': 'Marie',
            'last_name': 'Martin',
            'birth_date': '1985-05-15',
            'birth_place': 'Port-Gentil',
            'gender': 'F',
            'marital_status': 'MARRIED',
            'national_id': '987654321098',
            'phone_number': '+24107654321',
            'address_line1': '456 Avenue de l\'Indépendance',
            'city': 'Port-Gentil',
            'province': 'Ogooué-Maritime'
        }
        
        response = self.client.post('/identity/persons/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PersonIdentity.objects.count(), 1)
        
    def test_list_persons(self):
        """Test liste des personnes"""
        PersonIdentity.objects.create(
            first_name='Test',
            last_name='Person',
            birth_date=date(1990, 1, 1),
            birth_place='Test',
            gender='M',
            marital_status='SINGLE',
            national_id='111111111111',
            phone_number='+24101111111',
            address_line1='Test Address',
            city='Test City',
            province='Test Province',
            created_by=self.user
        )
        
        response = self.client.get('/identity/persons/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_validate_identity_action(self):
        """Test action de validation d'identité"""
        person = PersonIdentity.objects.create(
            first_name='Test',
            last_name='Validate',
            birth_date=date(1990, 1, 1),
            birth_place='Test',
            gender='M',
            marital_status='SINGLE',
            national_id='555555555555',
            phone_number='+24105555555',
            address_line1='Test Address',
            city='Test City',
            province='Test Province',
            created_by=self.user
        )
        
        response = self.client.post(f'/identity/persons/{person.id}/validate_identity/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        person.refresh_from_db()
        self.assertTrue(person.is_validated)

class DeduplicationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dedupuser', password='testpass')
        self.person1 = PersonIdentity.objects.create(
            first_name='Jean',
            last_name='Dupont',
            birth_date=date(1990, 1, 1),
            birth_place='Libreville',
            gender='M',
            marital_status='SINGLE',
            national_id='111111111111',
            phone_number='+24101111111',
            address_line1='Test Address 1',
            city='Libreville',
            province='Estuaire',
            created_by=self.user
        )
        self.person2 = PersonIdentity.objects.create(
            first_name='Jean',
            last_name='Dupond',  # Légère différence
            birth_date=date(1990, 1, 1),
            birth_place='Libreville',
            gender='M',
            marital_status='SINGLE',
            national_id='222222222222',
            phone_number='+24102222222',
            address_line1='Test Address 2',
            city='Libreville',
            province='Estuaire',
            created_by=self.user
        )
        
    def test_create_deduplication_candidate(self):
        """Test création candidat de déduplication"""
        candidate = DeduplicationCandidate.objects.create(
            person1=self.person1,
            person2=self.person2,
            similarity_score=0.8500,
            match_type='HIGH',
            matching_fields=['first_name', 'birth_date', 'city'],
            conflicting_fields=['last_name', 'national_id'],
            algorithm_version='1.0'
        )
        
        self.assertEqual(candidate.status, 'PENDING')
        self.assertEqual(float(candidate.similarity_score), 0.8500)

class FamilyRelationshipTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='familyuser', password='testpass')
        self.parent = PersonIdentity.objects.create(
            first_name='Pierre',
            last_name='Dupont',
            birth_date=date(1965, 1, 1),
            birth_place='Libreville',
            gender='M',
            marital_status='MARRIED',
            national_id='333333333333',
            phone_number='+24103333333',
            address_line1='Family Address',
            city='Libreville',
            province='Estuaire',
            created_by=self.user
        )
        self.child = PersonIdentity.objects.create(
            first_name='Jean',
            last_name='Dupont',
            birth_date=date(1990, 1, 1),
            birth_place='Libreville',
            gender='M',
            marital_status='SINGLE',
            national_id='444444444444',
            phone_number='+24104444444',
            address_line1='Family Address',
            city='Libreville',
            province='Estuaire',
            created_by=self.user
        )
        
    def test_create_family_relationship(self):
        """Test création relation familiale"""
        relationship = FamilyRelationship.objects.create(
            person1=self.parent,
            person2=self.child,
            relationship_type='PARENT',
            created_by=self.user
        )
        
        self.assertEqual(relationship.person1, self.parent)
        self.assertEqual(relationship.person2, self.child)
        self.assertEqual(relationship.relationship_type, 'PARENT')
        self.assertFalse(relationship.is_verified)



