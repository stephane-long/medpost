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
- **`merdier/`** : Répertoire contenant des fichiers temporaires ou de sauvegarde.

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
   APP_SECRET_KEY=<secret Flask API key>
   ```

   Créez un fichier `.env.prod` dans le répertoire `fetch_post` avec les variables suivantes :
   ```
   TZ=Europe/Paris
   DATABASE_PATH=/app/data/rss_qdm.db
   LOG_PATH=/app/logs/fetch_post.log
   API_KEY=<clé_api_x>
   API_KEY_SECRET=<secret_api_x>
   ACCESS_TOKEN=<jeton_d'accès_x>
   ACCESS_TOKEN_SECRET=<secret_du_jeton_d'accès_x>
   BLUESKY_LOGIN=<identifiant_bluesky>
   BLUESKY_PASSWORD=<mot_de_passe_bluesky>
   BLUESKY_URL_QDM=<URL du flux Bluesky>
   X_URL_QDM=<URL du flux X>
   QDM_URL_RSS=<url_du_flux_rss>
   IMAGES_PATH=/app/images/
   ```

4. **Lancer les services avec Docker Compose** :
   Accédez au répertoire `medpost-app` et démarrez les services :
   ```bash
   docker-compose up --build
   ```

5. **Accéder à l'application** :
   Ouvrez votre navigateur et accédez à `http://127.0.0.1:8000`.

## Utilisation

- **Connexion** : Utilisez la page de connexion pour vous authentifier.
- **Gérer les publications** : Créez, modifiez et supprimez des publications depuis le tableau de bord.
- **Programmer des publications** : Planifiez des publications pour des moments spécifiques et des réseaux donnés.
- **Gérer les tags** : Mettez à jour les tags pour les réseaux dans la section "Tags".
- **Récupérer les flux RSS** : Récupérez et affichez automatiquement les articles des flux RSS.
- **Automatisation** : Les publications planifiées sont automatiquement publiées sur les réseaux sociaux.

## Licence

Ce projet est sous licence MIT. Consultez le fichier `LICENSE` pour plus de détails.

## Remerciements

- [Flask](https://flask.palletsprojects.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Bootstrap](https://getbootstrap.com/)
- [Tweepy](https://www.tweepy.org/)
- [Feedparser](https://pythonhosted.org/feedparser/)
- [Docker](https://www.docker.com/)
