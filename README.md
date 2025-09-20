# Medpost

Medpost est une application basée sur Flask conçue pour gérer et automatiser la publication d'articles et de contenu sur diverses plateformes de médias sociaux. Elle inclut des fonctionnalités pour programmer des publications, gérer les tags pour les réseaux, et récupérer des flux RSS.

## Fonctionnalités

- **Authentification utilisateur** : Connexion et déconnexion sécurisées avec gestion des utilisateurs et des administrateurs.
- **Gestion des publications** : Créer, modifier, supprimer et programmer des publications pour différents réseaux sociaux.
- **Intégration des flux RSS** : Récupérer des articles à partir de flux RSS et les gérer dans l'application.
- **Tags des réseaux** : Gérer les tags spécifiques pour chaque réseau social.
- **Support multi-réseaux** : Supporte des plateformes comme X (anciennement Twitter), Bluesky et LinkedIn.
- **Interface dynamique** : Interface réactive et interactive utilisant Bootstrap.
- **Automatisation des publications** : Publier automatiquement les articles planifiés sur les réseaux sociaux.
- **Gestion des logs** : Centralisation des logs pour le suivi des activités et des erreurs.
- **Base de données SQLite** : Gestion des articles, publications et réseaux via SQLAlchemy.

## Structure du projet

- **`medpost-app/`** : Contient l'application Flask.
  - **`app.py`** : Logique principale de l'application et routes.
  - **`templates/`** : Modèles HTML pour l'interface utilisateur.
  - **`static/`** : Fichiers statiques comme CSS et JavaScript.
  - **`docker-compose.yml`** : Configuration Docker Compose pour orchestrer les services.
  - **`Dockerfile`** : Dockerfile pour construire l'image de l'application Flask.
- **`fetch_post/`** : Contient les scripts pour récupérer les flux RSS et automatiser les publications.
  - **`main.py`** : Script principal pour récupérer et publier du contenu.
  - **`database.py`** : Modèles de base de données et utilitaires pour la gestion des articles et des publications.
  - **`Dockerfile`** : Dockerfile pour construire l'image du service de récupération des flux RSS.
- **`data/`** : Contient les fichiers de base de données SQLite.
- **`logs/`** : Contient les fichiers de logs générés par l'application.

## Prérequis

- Python 3.9 ou supérieur
- Flask
- SQLAlchemy
- Tweepy (pour l'API X)
- Requests
- Feedparser
- Dotenv
- Docker et Docker Compose

## Instructions d'installation

1. **Cloner le dépôt** :
   ```bash
   git clone <repository-url>
   cd Medpost
   ```

2. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurer les variables d'environnement** :
   Créez un fichier `.env.prod` dans le répertoire `medpost-app` avec les variables suivantes :
   ```
   DATABASE_PATH=/app/data/rss_qdm.db
   LOG_PATH=/app/logs/medpost.log
   TZ=Europe/Paris
   APP_SECRET_KEY=<secret Flask API key>
   ```

   Créez un fichier `.env.prod` dans le répertoire `fetch_post` avec les variables suivantes :
   ```
   DATABASE_PATH=/app/data/rss_qdm.db
   LOG_PATH=/app/logs/medpost.log
   IMAGES_PATH=/app/images/
   TZ=Europe/Paris
   QDM_URL_RSS=https://www.lequotidiendumedecin.fr/rss.xml
   QPH_URL_RSS=https://www.lequotidiendupharmacien.fr/rss.xml
   #### QDM ####
   # Paramètres X QDM
   API_KEY_SECRET_QDM=
   API_KEY_QDM=
   ACCESS_TOKEN_QDM=
   ACCESS_TOKEN_SECRET_QDM=
   X_URL_QDM=https://x.com/leQdM/status/
   # Paramètres Bluesky QDM
   BLUESKY_LOGIN_QDM=lequotidiendumedecin.fr
   BLUESKY_PASSWORD_QDM=
   BLUESKY_URL_QDM=https://bsky.app/profile/lequotidiendumedecin.fr/post/
   #### QPH ####
   # Paramètres X QPH
   API_KEY_SECRET_QPH=
   API_KEY_QPH=
   ACCESS_TOKEN_QPH=
   ACCESS_TOKEN_SECRET_QPH=
   X_URL_QPH=https://x.com/leQPH_fr/status/
   # Paramètres Bluesky QPH
   BLUESKY_LOGIN_QPH=reseauxgps@gmail.com
   BLUESKY_PASSWORD_QPH=
   BLUESKY_URL_QPH=https://bsky.app/profile/leqph.bsky.social/post/
   ```

