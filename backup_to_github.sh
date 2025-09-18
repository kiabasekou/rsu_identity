#!/bin/bash

echo "🔄 SAUVEGARDE RSU IDENTITY VERS GITHUB"
echo "======================================"

# Initialiser git si nécessaire
if [ ! -d ".git" ]; then
    echo "📦 Initialisation du repository Git..."
    git init
    git branch -M main
fi

# Créer .gitignore
cat > .gitignore << 'GITIGNORE'
# Django
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# Django stuff
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Media files
media/

# Static files
staticfiles/

# Environment variables
.env
.env.local
.env.production

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Python
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
htmlcov/

# Node modules (pour le mobile)
node_modules/
.expo/
.expo-shared/
GITIGNORE

# Ajouter tous les fichiers
echo "📁 Ajout des fichiers..."
git add .

# Commit avec message descriptif
echo "💾 Commit des changements..."
COMMIT_MESSAGE="🚀 RSU Identity - Backend Django complet

✅ Apps créées:
- identity_app (Gestion identités, déduplication, relations familiales)
- programs_app (Programmes sociaux, bénéficiaires, paiements, bons numériques)
- surveys (Enquêtes et collecte de données)

✅ Fonctionnalités:
- Modèles Django complets avec contraintes
- APIs REST avec ViewSets
- Interface Admin personnalisée
- Serializers pour APIs
- Gestion des relations entre modèles

✅ Standards de qualité:
- Validation des données
- Index de base de données
- Contraintes de cohérence
- Documentation dans le code

🎯 Prochaines étapes:
- Configuration PostgreSQL
- Authentification JWT
- Tests unitaires
- Déploiement cloud"

git commit -m "$COMMIT_MESSAGE"

# Ajouter remote GitHub si nécessaire
if ! git remote get-url origin > /dev/null 2>&1; then
    echo "🔗 Ajout du remote GitHub..."
    git remote add origin https://github.com/kiabasekou/rsu_identity.git
fi

# Push vers GitHub
echo "🚀 Push vers GitHub..."
git push -u origin main