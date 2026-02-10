# Scripts de Migration

Ce répertoire contient les scripts nécessaires pour migrer la base de données de SQLite vers PostgreSQL.

## Scripts disponibles

### 1. `export_sqlite_data.py`

Exporte les données de la base SQLite vers un fichier JSON.

**Usage:**
```bash
python export_sqlite_data.py
```

**Sortie:**
- Fichier `../data/sqlite_export.json` contenant toutes les données

**Prérequis:**
- La base SQLite doit exister dans `../data/rss_qdm.db`

---

### 2. `import_to_postgres.py`

Importe les données JSON dans PostgreSQL.

**Usage:**
```bash
export DB_PASSWORD="your_password"
python import_to_postgres.py
```

**Variables d'environnement requises:**
- `DB_PASSWORD` : Mot de passe PostgreSQL (obligatoire)
- `DB_HOST` : Hôte PostgreSQL (défaut: localhost)
- `DB_PORT` : Port PostgreSQL (défaut: 5432)
- `DB_NAME` : Nom de la base (défaut: medpost_db)
- `DB_USER` : Utilisateur PostgreSQL (défaut: medpost_user)

**Prérequis:**
- PostgreSQL doit être accessible
- Le fichier `../data/sqlite_export.json` doit exister
- Le module `psycopg2` doit être installé

---

### 3. `backup_postgres.sh`

Crée une sauvegarde compressée de la base PostgreSQL.

**Usage:**
```bash
./backup_postgres.sh
```

**Sortie:**
- Fichier `../backups/medpost_db_YYYYMMDD_HHMMSS.sql.gz`
- Suppression automatique des sauvegardes > 7 jours

**Prérequis:**
- Le conteneur `medpost-postgres` doit être en cours d'exécution
- `pg_dump` doit être disponible dans le conteneur

---

### 4. `migrate_sqlite_to_postgres.load`

Configuration pgloader pour migration automatisée.

**Usage:**
```bash
# Éditer le fichier pour mettre à jour le mot de passe
nano migrate_sqlite_to_postgres.load

# Lancer la migration
pgloader migrate_sqlite_to_postgres.load
```

**Prérequis:**
- `pgloader` doit être installé
- PostgreSQL doit être accessible
- La base SQLite doit exister

---

## Workflow de migration recommandé

### Option A : Avec pgloader (recommandé)

```bash
# 1. Installer pgloader
sudo apt-get install pgloader  # Ubuntu/Debian
brew install pgloader           # macOS

# 2. Modifier le fichier de configuration
nano migrate_sqlite_to_postgres.load
# Mettre à jour le mot de passe dans l'URL PostgreSQL

# 3. Lancer la migration
pgloader migrate_sqlite_to_postgres.load

# 4. Vérifier
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db -c "\dt"
```

### Option B : Avec les scripts Python

```bash
# 1. Exporter depuis SQLite
python export_sqlite_data.py

# 2. Vérifier l'export
ls -lh ../data/sqlite_export.json
cat ../data/sqlite_export.json | jq '.articles_rss | length'

# 3. Configurer les credentials PostgreSQL
export DB_PASSWORD="your_password"
export DB_HOST="localhost"
export DB_PORT="5432"

# 4. Importer dans PostgreSQL
python import_to_postgres.py

# 5. Vérifier l'import
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db \
  -c "SELECT COUNT(*) FROM articles_rss;"
```

---

## Sauvegardes

### Sauvegarde manuelle

```bash
./backup_postgres.sh
```

### Sauvegarde automatique (cron)

```bash
# Éditer crontab
crontab -e

# Ajouter cette ligne pour une sauvegarde quotidienne à 2h du matin
0 2 * * * /path/to/medpost/scripts/backup_postgres.sh
```

### Restauration

```bash
# Décompresser et restaurer
gunzip -c ../backups/medpost_db_20240210_020000.sql.gz | \
  docker exec -i medpost-postgres psql -U medpost_user -d medpost_db
```

---

## Dépannage

### "Module psycopg2 not found"

```bash
pip install psycopg2-binary
```

### "Permission denied"

```bash
chmod +x *.sh *.py
```

### "Database not found"

Vérifiez que PostgreSQL est démarré et accessible :

```bash
docker ps | grep postgres
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db
```

### "Connection refused"

Vérifiez la configuration réseau Docker :

```bash
docker network inspect medpost-network
```

---

## Voir aussi

- [MIGRATION_SQLITE_TO_POSTGRESQL.md](../MIGRATION_SQLITE_TO_POSTGRESQL.md) - Guide complet de migration
- [MIGRATION_CHECKLIST.md](../MIGRATION_CHECKLIST.md) - Checklist étape par étape
