# Checklist de Migration SQLite vers PostgreSQL

Utilisez cette checklist pour suivre votre progression lors de la migration. Cochez chaque étape une fois complétée.

## Phase de Préparation

- [ ] Lire le guide complet [MIGRATION_SQLITE_TO_POSTGRESQL.md](MIGRATION_SQLITE_TO_POSTGRESQL.md)
- [ ] Créer une sauvegarde de la base SQLite actuelle
  ```bash
  cp data/rss_qdm.db data/rss_qdm.db.backup
  ```
- [ ] Sauvegarder les volumes Docker
  ```bash
  mkdir -p backup
  docker run --rm -v data_volume:/source -v $(pwd)/backup:/backup \
    alpine tar czf /backup/data_volume_backup.tar.gz -C /source .
  ```
- [ ] Tester les scripts sur un environnement de développement/test
- [ ] Planifier une fenêtre de maintenance
- [ ] Informer les utilisateurs de l'interruption de service

## Phase d'Installation PostgreSQL

- [ ] Installer Docker et Docker Compose (si pas déjà fait)
- [ ] Créer les variables d'environnement
  ```bash
  export POSTGRES_PASSWORD="votre_mot_de_passe_securise"
  export PGADMIN_PASSWORD="votre_mot_de_passe_admin"
  ```
- [ ] Lancer PostgreSQL avec `postgres-docker-compose.yml`
  ```bash
  docker-compose -f postgres-docker-compose.yml up -d
  ```
- [ ] Vérifier que PostgreSQL est démarré
  ```bash
  docker logs medpost-postgres
  docker exec -it medpost-postgres psql -U medpost_user -d medpost_db
  ```

## Phase de Migration des Données

Choisissez UNE des trois méthodes ci-dessous :

### Méthode A : pgloader (Recommandée pour grands volumes)

- [ ] Installer pgloader
  ```bash
  # Ubuntu/Debian
  sudo apt-get install pgloader
  
  # macOS
  brew install pgloader
  ```
- [ ] Modifier le fichier `scripts/migrate_sqlite_to_postgres.load` avec vos credentials
- [ ] Lancer pgloader
  ```bash
  pgloader scripts/migrate_sqlite_to_postgres.load
  ```
- [ ] Vérifier la migration
  ```bash
  psql -h localhost -U medpost_user -d medpost_db -c "\dt"
  ```

### Méthode B : Scripts Python

- [ ] Exporter les données SQLite vers JSON
  ```bash
  python scripts/export_sqlite_data.py
  ```
- [ ] Vérifier le fichier `data/sqlite_export.json`
- [ ] Configurer les variables d'environnement PostgreSQL
  ```bash
  export DB_PASSWORD="your_secure_password"
  export DB_HOST="localhost"
  export DB_PORT="5432"
  export DB_NAME="medpost_db"
  export DB_USER="medpost_user"
  ```
- [ ] Importer les données dans PostgreSQL
  ```bash
  python scripts/import_to_postgres.py
  ```

### Méthode C : Dump/Restore Manuel

- [ ] Créer un dump SQL de SQLite
- [ ] Adapter le SQL pour PostgreSQL
- [ ] Importer dans PostgreSQL

## Phase de Mise à Jour du Code

- [ ] Ajouter `psycopg2-binary==2.9.9` à `requirements.txt`
- [ ] Mettre à jour `fetch_post/database.py` (voir guide section 3.1)
- [ ] Mettre à jour `fetch_post/main.py` (voir guide section 3.2)
- [ ] Mettre à jour `medpost-app/app.py` (voir guide section 3.3)
- [ ] Créer `.env.prod` pour medpost-app avec configuration PostgreSQL
  ```bash
  DB_TYPE=postgresql
  DB_HOST=medpost-postgres
  DB_PORT=5432
  DB_NAME=medpost_db
  DB_USER=medpost_user
  DB_PASSWORD=your_secure_password_here
  ```
- [ ] Créer `.env.prod` pour fetch_post avec configuration PostgreSQL
- [ ] Mettre à jour `medpost-app/Dockerfile` (ajouter dépendances PostgreSQL)
- [ ] Mettre à jour `fetch_post/Dockerfile` (ajouter dépendances PostgreSQL)
- [ ] Mettre à jour `medpost-app/docker-compose.yml` (ajouter service PostgreSQL)

## Phase de Déploiement

- [ ] Arrêter les services existants
  ```bash
  cd medpost-app
  docker-compose down
  ```
- [ ] Reconstruire les images Docker
  ```bash
  docker-compose build --no-cache
  ```
- [ ] Démarrer les nouveaux services
  ```bash
  docker-compose up -d
  ```
- [ ] Vérifier les logs
  ```bash
  docker-compose logs -f medpost-app
  docker-compose logs -f fetcher-app
  ```

## Phase de Tests et Validation

- [ ] Tester la connexion PostgreSQL
  ```bash
  docker exec -it medpost-postgres psql -U medpost_user -d medpost_db -c "SELECT COUNT(*) FROM articles_rss;"
  ```
- [ ] Vérifier l'intégrité des données
  ```bash
  # Comparer les comptes entre SQLite et PostgreSQL
  sqlite3 data/rss_qdm.db "SELECT COUNT(*) FROM articles_rss;"
  docker exec -it medpost-postgres psql -U medpost_user -d medpost_db -c "SELECT COUNT(*) FROM articles_rss;"
  ```
- [ ] Tester l'interface web
  - [ ] Se connecter à http://localhost:5000
  - [ ] Vérifier l'affichage des articles
  - [ ] Créer une nouvelle publication de test
  - [ ] Uploader une image
  - [ ] Programmer une publication
- [ ] Tester le service fetcher
  - [ ] Vérifier les logs de récupération RSS
  - [ ] Vérifier la programmation des publications
- [ ] Tester les fonctionnalités critiques
  - [ ] Authentification utilisateur
  - [ ] Gestion des tokens
  - [ ] Publication sur les réseaux sociaux (mode test)

## Phase d'Optimisation

- [ ] Créer les index de performance
  ```sql
  docker exec -it medpost-postgres psql -U medpost_user -d medpost_db
  
  CREATE INDEX idx_articles_rss_nid ON articles_rss(nid);
  CREATE INDEX idx_articles_rss_pubdate ON articles_rss(pubdate);
  CREATE INDEX idx_articles_rss_newspaper ON articles_rss(newspaper);
  CREATE INDEX idx_posts_status ON posts(status);
  CREATE INDEX idx_posts_date_pub ON posts(date_pub);
  CREATE INDEX idx_posts_network ON posts(network);
  CREATE INDEX idx_tokens_metadata_network ON tokens_metadata(network, newspaper);
  CREATE INDEX idx_tokens_metadata_expires_at ON tokens_metadata(expires_at);
  
  ANALYZE articles_rss;
  ANALYZE posts;
  ANALYZE networks;
  ANALYZE tokens_metadata;
  ```
- [ ] Configurer les sauvegardes automatiques
  ```bash
  # Tester la sauvegarde manuelle
  ./scripts/backup_postgres.sh
  
  # Ajouter une tâche cron
  crontab -e
  # 0 2 * * * /path/to/medpost/scripts/backup_postgres.sh
  ```
- [ ] Configurer pgAdmin (optionnel)
  - [ ] Accéder à http://localhost:5050
  - [ ] Configurer le serveur PostgreSQL
- [ ] Sécuriser PostgreSQL en production
  - [ ] Retirer le mapping de port 5432 si non nécessaire
  - [ ] Utiliser des secrets Docker pour les mots de passe
  - [ ] Configurer SSL si nécessaire

## Phase de Monitoring

- [ ] Surveiller les performances pendant 24-48h
- [ ] Vérifier les logs régulièrement
  ```bash
  docker-compose logs -f
  tail -f logs/medpost.log
  ```
- [ ] Vérifier l'utilisation des ressources
  ```bash
  docker stats
  ```
- [ ] Documenter tout problème rencontré

## Phase de Documentation

- [ ] Mettre à jour la documentation interne avec les nouveaux credentials
- [ ] Documenter la nouvelle architecture PostgreSQL
- [ ] Former les autres développeurs/administrateurs
- [ ] Mettre à jour les runbooks opérationnels

## En Cas de Problème

Si quelque chose ne fonctionne pas :

- [ ] Consulter la section "Dépannage" du guide de migration
- [ ] Vérifier les logs Docker et PostgreSQL
- [ ] Exécuter la procédure de rollback si nécessaire
  ```bash
  # Arrêter les services
  docker-compose down
  
  # Restaurer la configuration SQLite
  git checkout .env.prod docker-compose.yml
  
  # Restaurer les données
  cp data/rss_qdm.db.backup data/rss_qdm.db
  
  # Redémarrer
  docker-compose up -d
  ```

## Post-Migration

- [ ] Conserver les sauvegardes SQLite pendant au moins 30 jours
- [ ] Mettre en place un monitoring régulier
- [ ] Planifier des revues de performance mensuelles
- [ ] Documenter les leçons apprises

---

**Date de début de migration** : ________________

**Date de fin de migration** : ________________

**Responsable** : ________________

**Notes** :
```
Utilisez cet espace pour noter tout problème, observation ou amélioration découverte pendant la migration.











```
