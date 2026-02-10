#!/bin/bash
# Backup PostgreSQL database

BACKUP_DIR="$(dirname "$0")/../backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/medpost_db_$TIMESTAMP.sql.gz"

# Créer le répertoire de sauvegarde
mkdir -p "$BACKUP_DIR"

# Backup avec pg_dump
docker exec medpost-postgres pg_dump -U medpost_user -d medpost_db | gzip > "$BACKUP_FILE"

echo "✅ Backup completed: $BACKUP_FILE"

# Nettoyer les anciennes sauvegardes (garder 7 jours)
find "$BACKUP_DIR" -name "medpost_db_*.sql.gz" -mtime +7 -delete
