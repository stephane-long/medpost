# Medpost

Medpost est une application basée sur Flask conçue pour gérer et automatiser la publication d'articles et de contenu sur diverses plateformes de médias sociaux. Elle inclut des fonctionnalités pour programmer des publications, gérer les tags pour les réseaux, et récupérer des flux RSS.

## Fonctionnalités

- **Authentification utilisateur** : Connexion et déconnexion sécurisées.
- **Gestion des publications** : Créer, modifier, supprimer et programmer des publications pour différents réseaux.
- **Intégration des flux RSS** : Récupérer des articles à partir de flux RSS et les gérer dans l'application.
- **Tags des réseaux** : Gérer les tags pour les réseaux sociaux.
- **Support multi-réseaux** : Supporte des plateformes comme X (anciennement Twitter), Bluesky et LinkedIn.
- **Interface dynamique** : Interface réactive et interactive utilisant Bootstrap.

## Structure du projet

- **`medpost-app/`** : Contient l'application Flask.
  - **`app.py`** : Logique principale de l'application et routes.
  - **`templates/`** : Modèles HTML pour l'interface utilisateur.
  - **`static/`** : Fichiers statiques comme CSS et JavaScript.
- **`fetch_post/`** : Contient les scripts pour récupérer les flux RSS et automatiser les publications.
  - **`main.py`** : Script principal pour récupérer et publier du contenu.
- **`database/`** : Modèles de base de données et utilitaires.

## Prérequis

- Python 3.8 ou supérieur
- Flask
- SQLAlchemy
- Tweepy (pour l'API X)
- Requests
- Feedparser
- Dotenv

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
   Créez un fichier `.env.prod` dans le répertoire medpost-app avec les variables suivantes :
   ```
   DATABASE_PATH=<chemin_vers_la_base_de_données>
   LOG_PATH=<chemin_vers_le_fichier_de_logs>
   APP_SECRET_KEY=<secret Flask API key>
   ```

Créez un fichier `.env.prod` dans le répertoire fetch_post avec les variables suivantes :
   ```
   TZ=<useau horaire :Europe/Paris>
   DATABASE_PATH=<chemin_vers_la_base_de_données>
   LOG_PATH=<chemin_vers_le_fichier_de_logs>
   API_KEY=<clé_api_x>
   API_KEY_SECRET=<secret_api_x>
   ACCESS_TOKEN=<jeton_d'accès_x>
   ACCESS_TOKEN_SECRET=<secret_du_jeton_d'accès_x>
   BLUESKY_LOGIN=<identifiant_bluesky>
   BLUESKY_PASSWORD=<mot_de_passe_bluesky>
   BLUESKY_URL_QDM=<URL du flux Bluesky>
   X_URL_QDM=<URL du flux X>
   QDM_URL_RSS=<url_du_flux_rss>
   IMAGES_PATH=<chemin_vers_les_images>
   ```


4. **Initialiser la base de données** :
   Exécutez la commande suivante pour créer la base de données et les tables :
   ```bash
   python -m fetch_post.main
   ```

5. **Lancer l'application** :
   Accédez au répertoire `medpost-app` et démarrez le serveur Flask :
   ```bash
   python app.py
   ```

6. **Accéder à l'application** :
   Ouvrez votre navigateur et accédez à `http://127.0.0.1:8000`.

## Utilisation

- **Connexion** : Utilisez la page de connexion pour vous authentifier.
- **Gérer les publications** : Créez, modifiez et supprimez des publications depuis le tableau de bord.
- **Programmer des publications** : Planifiez des publications pour des moments spécifiques et des réseaux donnés.
- **Gérer les tags** : Mettez à jour les tags pour les réseaux dans la section "Tags".
- **Récupérer les flux RSS** : Récupérez et affichez automatiquement les articles des flux RSS.

## Licence

Ce projet est sous licence MIT. Consultez le fichier `LICENSE` pour plus de détails.

## Remerciements

- [Flask](https://flask.palletsprojects.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Bootstrap](https://getbootstrap.com/)
- [Tweepy](https://www.tweepy.org/)
- [Feedparser](https://pythonhosted.org/feedparser/)
