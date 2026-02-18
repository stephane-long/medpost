# Architecture des services fetch_post

## Structure

Le service `fetch_post` a été divisé en deux services distincts pour améliorer la maintenabilité, la scalabilité et la résilience.

```
fetch_post/
├── rss_fetcher/          # Service de lecture des flux RSS
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── database.py      # Lien symbolique vers ../database.py
└── social_publisher/     # Service de publication sur les réseaux sociaux
    ├── Dockerfile
    ├── requirements.txt
    ├── main.py
    └── database.py      # Lien symbolique vers ../database.py
```

## Services

### 1. rss_fetcher

**Rôle** : Lecture des flux RSS et stockage des articles en base de données

**Fonctionnalités** :
- Récupération des flux RSS depuis QDM et QPH
- Extraction des métadonnées des articles (titre, lien, résumé, image)
- Stockage en base de données SQLite
- Gestion des erreurs et retry automatique
- Respect des délais entre requêtes (crawl delay)

**Commande d'exécution** :
```bash
python main.py
```

**Variables d'environnement requises** :
- `QDM_URL_RSS` : URL du flux RSS du Quotidien du Médecin
- `QPH_URL_RSS` : URL du flux RSS du Quotidien du Pharmacien
- `DATABASE_PATH` : Chemin vers la base de données
- `LOG_PATH` : Chemin vers le fichier de logs
- `IMAGES_PATH` : Chemin vers les images
- `CRAWL_DELAY` : Délai entre requêtes (défaut: 1.5 secondes)
- `BOT_NAME`, `BOT_VERSION`, `BOT_CONTACT` : Configuration du User-Agent

### 2. social_publisher

**Rôle** : Publication des posts sur les réseaux sociaux

**Fonctionnalités** :
- Récupération des posts planifiés depuis la base de données
- Publication sur X (Twitter), Bluesky et Threads
- Gestion des tokens d'accès (avec renouvellement automatique pour Threads)
- Upload des images sur les réseaux sociaux
- Mise à jour du statut des posts après publication
- Migration des tokens Threads depuis .env vers la base de données

**Commande d'exécution** :
```bash
python main.py
```

**Variables d'environnement requises** :
- `DATABASE_PATH` : Chemin vers la base de données
- `LOG_PATH` : Chemin vers le fichier de logs
- `IMAGES_PATH` : Chemin vers les images
- `API_KEY_*`, `API_KEY_SECRET_*`, `ACCESS_TOKEN_*`, `ACCESS_TOKEN_SECRET_*` : Credentials X (Twitter)
- `BLUESKY_LOGIN_*`, `BLUESKY_PASSWORD_*` : Credentials Bluesky
- `THREADS_TOKEN_*` : Tokens Threads (pour migration initiale)
- `X_URL_*`, `BLUESKY_URL_*` : URLs de base pour les liens vers les posts
- `HOSTNAME_FTP_BUCKET`, `LOGIN_HOST_BUCKET`, `PWD_HOST_BUCKET`, `PORT_BUCKET` : Configuration SFTP pour Threads
- `BUCKET_PATH`, `BUCKET_URL` : Configuration du bucket de stockage temporaire

## Configuration Docker

Les deux services sont orchestrés via le fichier `docker-compose.yml` situé dans `medpost-app/`.

### Commandes Docker

**Construction et démarrage des services** :
```bash
cd medpost-app
docker-compose up -d --build
```

**Arrêt des services** :
```bash
docker-compose down
```

**Voir les logs** :
```bash
docker-compose logs -f rss-fetcher
docker-compose logs -f social-publisher
```

## Configuration Cron

Les deux services sont conçus pour être exécutés périodiquement via un cron job. Voici un exemple de configuration cron pour exécuter les services toutes les 5 minutes :

```bash
# Exécution du service RSS Fetcher toutes les 5 minutes
*/5 * * * * cd /chemin/vers/medpost/medpost-app && docker-compose run --rm rss-fetcher

# Exécution du service Social Publisher toutes les 5 minutes
*/5 * * * * cd /chemin/vers/medpost/medpost-app && docker-compose run --rm social-publisher
```

## Migration depuis l'ancienne architecture

Pour migrer depuis l'ancienne architecture (service unique) :

1. **Sauvegarder la base de données** :
   ```bash
   cp data/rss_qdm.db data/rss_qdm.db.backup
   ```

2. **Mettre à jour le docker-compose.yml** :
   Le fichier a déjà été mis à jour pour inclure les deux nouveaux services.

3. **Vérifier les variables d'environnement** :
   Assurez-vous que toutes les variables nécessaires sont présentes dans `fetch_post/.env.dev`

4. **Lancer les nouveaux services** :
   ```bash
   cd medpost-app
   docker-compose up -d --build
   ```

5. **Vérifier les logs** :
   ```bash
   docker-compose logs -f
   ```

## Avantages de la nouvelle architecture

1. **Séparation des responsabilités** : Chaque service a un rôle unique et bien défini
2. **Scalabilité indépendante** : Peut scaler la lecture des flux sans impacter la publication
3. **Résilience améliorée** : Un échec dans un service n'affecte pas l'autre
4. **Déploiement indépendant** : Mise à jour d'un service sans redémarrer l'autre
5. **Monitoring granulaire** : Logs et métriques séparés pour chaque service
6. **Maintenabilité** : Code plus simple à comprendre et à maintenir

## Dépannage

### Problèmes courants

**Problème** : Le service RSS Fetcher ne récupère pas les articles
- **Solution** : Vérifier l'URL du flux RSS, les permissions réseau, et les logs

**Problème** : Le service Social Publisher ne publie pas les posts
- **Solution** : Vérifier les credentials des réseaux sociaux, les quotas API, et les logs

**Problème** : Erreur de connexion à la base de données
- **Solution** : Vérifier le chemin dans `DATABASE_PATH` et les permissions sur le volume

**Problème** : Token Threads expiré
- **Solution** : Le service vérifie automatiquement et renouvelle le token si nécessaire (moins de 7 jours avant expiration)

### Vérification de l'état

Pour vérifier que les services fonctionnent correctement :

1. **Vérifier les logs** :
   ```bash
   docker-compose logs rss-fetcher
   docker-compose logs social-publisher
   ```

2. **Vérifier la base de données** :
   ```bash
   docker-compose run --rm sqlite-cli
   ```
   Puis dans sqlite :
   ```sql
   SELECT COUNT(*) FROM articles_rss;
   SELECT COUNT(*) FROM posts WHERE status = 'plan';
   ```

3. **Vérifier les containers** :
   ```bash
   docker ps -a
   ```
