# Medpost 🚀

Medpost est une **plateforme d'automatisation de publications sur les réseaux sociaux** basée sur Flask et Docker. Elle est conçue pour automatiser la récupération d'articles RSS des journaux médicaux français (Le Quotidien du Médecin et Le Quotidien du Pharmacien) et leur publication automatique sur plusieurs plateformes (X, Bluesky, Threads).

## Fonctionnalités principales

### 📰 Gestion du contenu
- **Récupération RSS automatisée** : Ingestion continue des flux RSS des journaux médicaux
- **Gestion des articles** : Stockage, indexation et déduplication des articles via l'ID Drupal (`nid`)
- **Création de publications** : Interface pour créer et programmer des publications vers plusieurs réseaux sociaux
- **Upload d'images** : Support des images personnalisées pour chaque publication

### 🔐 Authentification & Sécurité
- **Gestion des utilisateurs** : Connexion/déconnexion sécurisées avec hachage de mots de passe
- **Rôles administrateur** : Distinction entre utilisateurs standards et administrateurs
- **Gestion des tokens** : Système automatisé de renouvellement des tokens d'accès (notamment pour Threads)
- **Environnements distincts** : Configuration séparée pour développement et production

### 📡 Intégration multi-réseaux
- **X (Twitter)** : Publication via API Tweepy avec authentification OAuth1
- **Bluesky** : Publication native via AT Protocol
- **Threads** : Publication avec gestion automatisée des tokens 60j
- **Tags personnalisés** : Configuration de tags spécifiques par réseau social

### ⚙️ Automatisation
- **Tâches planifiées** : Publication automatique des articles programmés
- **Renouvellement tokens** : Système de renouvellement proactif des tokens d'accès (7j avant expiration)
- **Retry automatique** : Stratégie de retry avec backoff exponentiel pour les requêtes réseau
- **Logging centralisé** : Suivi complet des activités et erreurs dans `medpost.log`

### 💾 Gestion des données
- **Base de données SQLite** : Stockage persistent via SQLAlchemy
- **Modèles principaux** : Articles_rss, Posts, Networks, Users, TokensMetadata
- **Volumes Docker** : Partage des données entre conteneurs pour persistence

## Architecture

### Architecture à deux services

L'application s'exécute sous **Docker Compose** avec trois conteneurs principaux :

```
┌─────────────────────────────────────────────────────┐
│               Docker Compose                         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────┐  ┌──────────────────┐         │
│  │   medpost-app    │  │   fetcher-app    │         │
│  │   (Flask Web UI) │  │  (Background)    │         │
│  │                  │  │                  │         │
│  │ - Routes HTTP    │  │ - RSS Fetching   │         │
│  │ - DB Management  │  │ - Auto Publishing│         │
│  │ - User Auth      │  │ - Token Mgmt     │         │
│  └──────────────────┘  └──────────────────┘         │
│          ▲                      ▲                     │
│          └──────────┬───────────┘                     │
│                     │ (Shared Volumes)               │
│          ┌──────────▼──────────┐                     │
│          │  Volumes Docker     │                     │
│          │ ───────────────     │                     │
│          │ data_volume         │                     │
│          │  (rss_qdm.db)       │                     │
│          │ logs_volume         │                     │
│          │  (medpost.log)      │                     │
│          │ images_volume       │                     │
│          │  (pictures)         │                     │
│          └─────────────────────┘                     │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Services

#### 1. **medpost-app** (Flask Web UI)
- Interface web pour créer, éditer et programmer les publications
- Gestion des utilisateurs et authentification
- Visualisation des articles RSS
- Upload d'images
- Configuration des réseaux sociaux et tags

#### 2. **fetcher-app** (Background Service)
- Récupération automatique des flux RSS
- Publication automatisée sur les réseaux sociaux
- Gestion et renouvellement des tokens d'accès
- Gestion des erreurs et retry automatique

#### 3. **Volumes partagés**
- `data_volume` : Base de données SQLite (`rss_qdm.db`)
- `logs_volume` : Logs centralisés (`medpost.log`)
- `images_volume` : Images des publications

## Structure de la base de données

### Modèles principaux (SQLAlchemy)

#### **Articles_rss**
Articles récupérés via les flux RSS avec métadonnées complètes.

| Champ | Type | Description |
|-------|------|-------------|
| id | Integer | Clé primaire |
| nid | Integer | **ID Drupal du journal** (clé pour déduplication) |
| title | Text | Titre de l'article |
| link | Text | URL vers l'article original |
| summary | Text | Résumé/description |
| image_url | Text | URL de l'image |
| pubdate | DateTime | Date de publication |
| online | Integer | Statut publication |
| newspaper | Text | Journal source (QDM/QPH) |

#### **Posts**
Publications programmées/publiées sur les réseaux sociaux.

| Champ | Type | Description |
|-------|------|-------------|
| id | Integer | Clé primaire |
| article_id | Integer | Référence vers Articles_rss |
| network | Text | Réseau social (x/bluesky/threads) |
| status | String | État (plan/pub) |
| scheduled_at | DateTime | Date de publication prévue |
| published_at | DateTime | Date de publication réelle |
| content | Text | Contenu de la publication |

#### **Networks**
Configuration des réseaux sociaux avec tags personnalisés.

| Champ | Type | Description |
|-------|------|-------------|
| id | Integer | Clé primaire |
| name | String | Nom du réseau |
| tags | String | Tags spécifiques |
| is_active | Boolean | Réseau actif |

#### **TokensMetadata** *(nouveau)*
Gestion centralisée et automatisée des tokens d'accès.

| Champ | Type | Description |
|-------|------|-------------|
| id | Integer | Clé primaire |
| network | String | Réseau (threads) |
| newspaper | String | Journal (qdm/qph) |
| access_token | String | Token actuel |
| expires_at | DateTime | Expiration du token |
| is_active | Boolean | Token actif |
| last_refresh_date | DateTime | Dernier renouvellement |

## Prérequis

### Environnement
- **Python** 3.9+ (pour développement local)
- **Docker** 20.10+
- **Docker Compose** 2.0+

### Dépendances principales

**Backend (fetch_post) :**
- SQLAlchemy 2.0.38 - ORM de base de données
- Tweepy 4.15.0 - API X (Twitter)
- atproto 0.0.59 - API Bluesky (AT Protocol)
- Feedparser 6.0.11 - Parsing RSS/Atom
- Requests 2.32.3 - Requêtes HTTP
- BeautifulSoup4 4.14.3 - Web scraping
- Paramiko 4.0.0 - SSH (gestion distante)

**Frontend (medpost-app) :**
- Flask 2.0.3 - Framework web
- Flask-Login 0.5.0 - Gestion sessions
- Flask-SQLAlchemy 2.5.1 - Intégration BD
- SQLAlchemy 1.4.27 - ORM
- Pillow 11.2.1 - Traitement images
- Gunicorn 20.1.0 - Serveur WSGI production

## Installation et démarrage

### 1. Préparation du projet

```bash
# Cloner le dépôt
git clone https://github.com/stephane-long/medpost.git
cd Medpost

# Créer les répertoires nécessaires
mkdir -p data logs images
```

### 2. Configuration des variables d'environnement

**Fichier : `.env.prod` (medpost-app/)**
```bash
# Chemins et configuration de base
DATABASE_PATH=/app/data/rss_qdm.db
LOG_PATH=/app/logs/medpost.log
TZ=Europe/Paris
APP_SECRET_KEY=your-secret-key-here

# Docker
DOCKER_ENV=true
```

**Fichier : `.env.prod` (fetch_post/)**
```bash
# Chemins
DATABASE_PATH=/app/data/rss_qdm.db
LOG_PATH=/app/logs/medpost.log
IMAGES_PATH=/app/images/
TZ=Europe/Paris

# Flux RSS
QDM_URL_RSS=https://www.lequotidiendumedecin.fr/rss.xml
QPH_URL_RSS=https://www.lequotidiendupharmacien.fr/rss.xml

# === QUOTIDIEN DU MEDECIN (QDM) ===
# Paramètres X/Twitter
API_KEY_QDM=your_api_key
API_KEY_SECRET_QDM=your_api_secret
ACCESS_TOKEN_QDM=your_access_token
ACCESS_TOKEN_SECRET_QDM=your_access_token_secret
X_URL_QDM=https://x.com/leQdM/status/

# Paramètres Bluesky
BLUESKY_LOGIN_QDM=medecin@bsky.social
BLUESKY_PASSWORD_QDM=your_password
BLUESKY_URL_QDM=https://bsky.app/profile/medecin.bsky.social/post/

# Paramètres Threads
THREADS_TOKEN_QDM=your_threads_token
THREADS_URL_QDM=https://threads.net/...

# === QUOTIDIEN DU PHARMACIEN (QPH) ===
# Configuration similaire pour QPH
API_KEY_QPH=...
# ... etc
```

### 3. Initialisation des volumes et données

```bash
# Initialiser les volumes Docker
docker volume create data_volume
docker volume create logs_volume
docker volume create images_volume

# Copier les fichiers initiaux si existants
docker run --rm -v data_volume:/data \
  -v $(pwd)/data:/host alpine cp /host/rss_qdm.db /data/ 2>/dev/null || true

docker run --rm -v logs_volume:/data \
  -v $(pwd)/logs:/host alpine touch /data/medpost.log

docker run --rm -v images_volume:/data \
  -v $(pwd)/images:/host alpine cp /host/no_picture.jpg /data/ 2>/dev/null || true
```

### 4. Lancer l'application

```bash
# De préférence, se placer dans medpost-app/
cd medpost-app

# Construire et démarrer les services
docker-compose up --build -d

# Vérifier les logs
docker-compose logs -f

# Arrêter les services
docker-compose down
```

### 5. Accès à l'application

- **Interface web** : http://localhost:5000
- **Identifiants par défaut** : À configurer via la BD

## Utilisation

### Interface web (medpost-app)

1. **Se connecter** avec ses identifiants
2. **Visualiser les articles** récupérés des flux RSS
3. **Créer une publication** : 
   - Sélectionner un article
   - Ajouter un titre personnalisé (optionnel)
   - Choisir les réseaux de destination
   - Programmer la date/heure de publication
   - Importer une image (optionnel)
4. **Programmer les publications** pour les réseaux sélectionnés

### Service d'automatisation (fetcher-app)

Le service tourne continuellement en arrière-plan et :

1. **Récupère les flux RSS** à intervalle régulier (configurable)
2. **Déduplique les articles** via l'ID Drupal (`nid`)
3. **Renouvelle les tokens** expirés (notamment Threads) proactivement
4. **Publie automatiquement** les posts programmés sur les réseaux
5. **Gère les erreurs** avec retry automatique et backoff exponentiel
6. **Enregistre les activités** dans les logs centralisés

### Logs

Les logs sont centralisés dans `/logs/medpost.log` et conteneur les informations de :
- Récupération RSS
- Publication sur les réseaux
- Renouvellement de tokens
- Erreurs et debugging

```bash
# Consulter les logs en temps réel
docker-compose logs -f fetcher-app

# Ou directement le fichier
tail -f logs/medpost.log
```

## Gestion des tokens

Voir la documentation complète : [TOKENS_MANAGEMENT.md](TOKENS_MANAGEMENT.md)

### Renouvellement automatique

Les tokens (notamment Threads avec durée de vie 60j) sont **renouvelés automatiquement** 7 jours avant expiration :

```
✅ Pas d'intervention manuelle requise
✅ Historique complet dans la base de données
✅ Fallback sur .env en cas de problème
```

## Dépannage

### L'application ne démarre pas

```bash
# Vérifier les logs
docker-compose logs medpost-app

# S'assurer que les ports ne sont pas utilisés
lsof -i :5000

# Vérifier la configuration .env
cat medpost-app/.env.prod
```

### Les articles ne sont pas récupérés

```bash
# Vérifier les logs du fetcher
docker-compose logs fetcher-app

# Vérifier que les URLs RSS sont correctes
curl https://www.lequotidiendumedecin.fr/rss.xml

# Vérifier la base de données
docker run --rm -v data_volume:/data -it sqlite:latest sqlite3 /data/rss_qdm.db ".tables"
```

### Les publications ne s'envoient pas

1. Vérifier les **tokens d'authentification** dans `.env.prod`
2. Vérifier les **permissions** sur les comptes sociaux
3. Consulter les **logs** du fetcher pour les messages d'erreur
4. Vérifier que la **publication est programmée** avec une date future

## Documentation additionnelle

- **[CLAUDE.md](CLAUDE.md)** - Directives pour Claude (architecture détaillée)
- **[TOKENS_MANAGEMENT.md](TOKENS_MANAGEMENT.md)** - Gestion des tokens d'accès

## Contribution

Les contributions sont bienvenues ! Pour des changements majeurs, ouvrez d'abord une issue pour discuter des modifications proposées.

## Licence

Ce projet est licensié sous [LICENSE](LICENSE)

