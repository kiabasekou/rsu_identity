# 🇬🇦 RSU Identity - Système de Gestion des Identités et Programmes Sociaux

## 📋 Vue d'ensemble

**RSU Identity** est une solution complète de gestion des identités et des programmes sociaux pour le gouvernement gabonais. Le système permet la déduplication des bénéficiaires, la gestion des relations familiales, et l'administration des programmes d'aide sociale.

## 🏗️ Architecture

```
RSU Identity System
├── Backend Django (API REST)
│   ├── identity_app     → Gestion des identités
│   ├── programs_app     → Programmes sociaux
│   └── surveys          → Enquêtes et collecte
├── Frontend Mobile (React Native)
├── Base de données PostgreSQL
└── APIs d'intégration (RBPP, Payments)
```

## ⚡ Démarrage Rapide

### Prérequis
- Python 3.11+
- PostgreSQL 13+
- Node.js 18+ (pour mobile)
- Git

### Installation Backend

```bash
# Cloner le repository
git clone https://github.com/kiabasekou/rsu_identity.git
cd rsu_identity/backend

# Créer environnement virtuel
python -m venv rsu
source rsu/bin/activate  # Linux/Mac
# ou
rsu\Scripts\activate     # Windows

# Installer dépendances
pip install -r requirements.txt

# Configuration base de données
cp .env.example .env
# Modifier les variables dans .env

# Migrations
python manage.py migrate

# Créer superuser
python manage.py createsuperuser

# Lancer le serveur
python manage.py runserver
```

### URLs principales
- **Admin** : http://127.0.0.1:8000/admin/
- **API Identity** : http://127.0.0.1:8000/identity/
- **API Programs** : http://127.0.0.1:8000/programs/

## 📱 Modules Principaux

### 🆔 Identity App
- **PersonIdentity** : Identités uniques avec validation CNI gabonaise
- **DeduplicationCandidate** : Détection ML des doublons
- **FamilyRelationship** : Relations familiales vérifiées

### 🏛️ Programs App  
- **SocialProgram** : Programmes gouvernementaux avec budget
- **Beneficiary** : Bénéficiaires avec scores d'éligibilité
- **Payment** : Paiements multi-canaux (mobile money, virements)
- **DigitalVoucher** : Bons numériques avec QR codes

### 📊 Surveys App
- **SurveyTemplate** : Modèles d'enquêtes configurables
- **SurveySession** : Sessions de collecte terrain
- **DataQuality** : Validation et contrôle qualité

## 🔧 Technologies

- **Backend** : Django 5.0, Django REST Framework
- **Base de données** : PostgreSQL 13+ avec extensions JSON
- **Frontend Mobile** : React Native + Expo
- **APIs** : RESTful avec documentation Swagger
- **Authentification** : JWT + OAuth2
- **Monitoring** : Logging structuré + Sentry

## 🚀 Fonctionnalités Clés

### ✅ Gestion des Identités
- Déduplication automatique ML
- Validation CNI gabonaise
- Géolocalisation précise
- Relations familiales

### ✅ Programmes Sociaux
- Calcul automatique d'éligibilité
- Scores de vulnérabilité
- Paiements multi-canaux
- Bons numériques QR

### ✅ Collecte Mobile
- Mode offline-first
- Synchronisation intelligente
- Validation terrain
- Géotag automatique

## 📈 Roadmap

- [x] **Phase 1** : Backend Django + Modèles
- [ ] **Phase 2** : APIs REST + Authentication
- [ ] **Phase 3** : Mobile React Native
- [ ] **Phase 4** : Intégrations (RBPP, Payments)
- [ ] **Phase 5** : Déploiement Production

## 🤝 Contribution

1. Fork le repository
2. Créer une branche feature (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push vers la branche (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT - voir [LICENSE](LICENSE) pour plus de détails.

## 📞 Contact

- **Équipe** : RSU Digital Team
- **Email** : souare.ahmed@gmail.com
- **Repository** : https://github.com/kiabasekou/rsu_identity

---

**🇬🇦 Développé avec ❤️ pour le Gabon Digital**