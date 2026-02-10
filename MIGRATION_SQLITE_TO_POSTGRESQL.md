# Migration de SQLite vers PostgreSQL 🔄

Ce guide détaille les étapes nécessaires pour migrer la base de données Medpost de **SQLite** vers **PostgreSQL**.

## Table des matières

1. [Pourquoi migrer vers PostgreSQL ?](#pourquoi-migrer-vers-postgresql)
2. [Prérequis](#prérequis)
3. [Étape 1 : Installation de PostgreSQL](#étape-1--installation-de-postgresql)
4. [Étape 2 : Mise à jour des dépendances Python](#étape-2--mise-à-jour-des-dépendances-python)
5. [Étape 3 : Modifications du code](#étape-3--modifications-du-code)
6. [Étape 4 : Configuration Docker](#étape-4--configuration-docker)
7. [Étape 5 : Migration des données](#étape-5--migration-des-données)
8. [Étape 6 : Tests et validation](#étape-6--tests-et-validation)
9. [Retour arrière (Rollback)](#retour-arrière-rollback)
10. [Recommandations post-migration](#recommandations-post-migration)

---

## Pourquoi migrer vers PostgreSQL ?

### Avantages de PostgreSQL par rapport à SQLite

| Critère | SQLite | PostgreSQL |
|---------|--------|------------|
| **Concurrence** | Verrouillage au niveau fichier | Support complet MVCC avec verrous au niveau ligne |
| **Scalabilité** | Limitée (fichier unique) | Excellente (serveur dédié) |
| **Intégrité des données** | Basique | Contraintes avancées (CHECK, EXCLUDE) |
| **Performances** | Bonnes pour petites BDs | Optimisées pour grands volumes |
| **Types de données** | Limités | Riches (JSON, ARRAY, UUID, etc.) |
| **Sauvegarde** | Copie de fichier | pg_dump, réplication streaming |
| **Support production** | Non recommandé | Conçu pour production |

### Cas d'usage recommandant PostgreSQL

- **Accès concurrent** : Plusieurs services accédant simultanément (medpost-app + fetcher-app)
- **Volume de données** : Croissance importante attendue (milliers d'articles)
- **Intégrité transactionnelle** : Garanties ACID strictes
- **Environnement de production** : Déploiement professionnel

---

## Prérequis

### Logiciels nécessaires

- **Docker** 20.10+ et **Docker Compose** 2.0+
- **Python** 3.9+ (pour tests locaux)
- **psycopg2** (driver PostgreSQL pour Python)
- **pgloader** (outil de migration de données)

### Sauvegarde préalable

⚠️ **IMPORTANT** : Effectuer une sauvegarde complète avant toute modification

```bash
# Sauvegarder la base SQLite actuelle
cp data/rss_qdm.db data/rss_qdm.db.backup

# Sauvegarder les volumes Docker
docker run --rm -v data_volume:/source -v $(pwd)/backup:/backup \
  alpine tar czf /backup/data_volume_backup.tar.gz -C /source .

# Sauvegarder les logs et images
docker run --rm -v logs_volume:/source -v $(pwd)/backup:/backup \
  alpine tar czf /backup/logs_volume_backup.tar.gz -C /source .

docker run --rm -v images_volume:/source -v $(pwd)/backup:/backup \
  alpine tar czf /backup/images_volume_backup.tar.gz -C /source .
```

---

## Étape 1 : Installation de PostgreSQL

### Option A : Service PostgreSQL Docker (recommandé)

#### 1.1 Créer un fichier docker-compose pour PostgreSQL

Créer `postgres-docker-compose.yml` à la racine du projet :

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: medpost-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: medpost_db
      POSTGRES_USER: medpost_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - medpost-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medpost_user -d medpost_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: medpost-pgadmin
    restart: unless-stopped
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@medpost.local
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD:-admin}
      PGADMIN_CONFIG_SERVER_MODE: 'False'
    ports:
      - "5050:80"
    volumes:
      - pgadmin_data:/var/lib/pgadmin
    networks:
      - medpost-network
    depends_on:
      - postgres

volumes:
  postgres_data:
    driver: local
  pgadmin_data:
    driver: local

networks:
  medpost-network:
    driver: bridge
```

#### 1.2 Lancer PostgreSQL

```bash
# Définir un mot de passe sécurisé
export POSTGRES_PASSWORD="votre_mot_de_passe_securise"
export PGADMIN_PASSWORD="votre_mot_de_passe_admin"

# Démarrer PostgreSQL
docker-compose -f postgres-docker-compose.yml up -d

# Vérifier que PostgreSQL est prêt
docker logs medpost-postgres

# Se connecter pour vérifier
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db
```

### Option B : PostgreSQL local (alternative)

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# macOS (Homebrew)
brew install postgresql@16
brew services start postgresql@16

# Créer la base de données
sudo -u postgres psql
postgres=# CREATE DATABASE medpost_db;
postgres=# CREATE USER medpost_user WITH ENCRYPTED PASSWORD 'your_password';
postgres=# GRANT ALL PRIVILEGES ON DATABASE medpost_db TO medpost_user;
postgres=# \q
```

---

## Étape 2 : Mise à jour des dépendances Python

### 2.1 Ajouter psycopg2 aux requirements

Modifier `requirements.txt` :

```bash
# Ajouter cette ligne
psycopg2-binary==2.9.9

# Ou pour environnement de production
psycopg2==2.9.9
```

**Note** : 
- `psycopg2-binary` : précompilé, rapide pour dev/test
- `psycopg2` : nécessite compilation, recommandé pour production

### 2.2 Mettre à jour SQLAlchemy (optionnel mais recommandé)

SQLAlchemy 1.3.24 est ancien. Pour PostgreSQL, considérer une mise à jour :

```bash
# Dans requirements.txt
SQLAlchemy==2.0.38  # Version récente avec meilleurs supports PostgreSQL
```

⚠️ **Attention** : SQLAlchemy 2.0 introduit des changements de breaking changes. Voir [Guide de migration SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html).

Si vous gardez SQLAlchemy 1.3.24, assurez-vous de la compatibilité avec psycopg2.

---

## Étape 3 : Modifications du code

### 3.1 Modifier `fetch_post/database.py`

#### Option A : Avec gestion multi-base (recommandé)

```python
# /home/runner/work/medpost/medpost/fetch_post/database.py
import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


class Articles_rss(Base):
    __tablename__ = "articles_rss"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nid = Column(Integer, nullable=False)  # Node id Drupal
    title = Column(String, nullable=False)
    link = Column(String, nullable=False)
    summary = Column(String)
    image_url = Column(String)
    pubdate = Column(DateTime, nullable=False)
    online = Column(Integer, nullable=False)
    newspaper = Column(String, nullable=False)

    def __repr__(self):
        return f"Article {self.title} - {self.pubdate}"


class Posts(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    tagline = Column(String, nullable=False)
    image_url = Column(String)
    date_pub = Column(DateTime, nullable=False)
    status = Column(String, nullable=False)
    network_post_id = Column(Integer, nullable=True)
    id_article = Column(ForeignKey("articles_rss.id"))
    network = Column(ForeignKey("networks.id"))

    def __repr__(self):
        return f"Post sur {self.network} - {self.title} - {self.date_pub}"


class Networks(Base):
    __tablename__ = "networks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tag = Column(String, nullable=True)

    def __repr__(self):
        return f"Network {self.id} : {self.name}"


class TokensMetadata(Base):
    __tablename__ = "tokens_metadata"
    id = Column(Integer, primary_key=True, autoincrement=True)
    network = Column(String(50), nullable=False)
    newspaper = Column(String(10), nullable=False)
    access_token = Column(String(500), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    previous_token = Column(String(500), nullable=True)
    last_refresh_date = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"Token {self.network} - {self.newspaper} - expires: {self.expires_at}"


# Function to create the engine and the session
def create_db_and_tables(database_url=None):
    """
    Create database engine and tables.
    
    Args:
        database_url: Database URL. If None, constructs from environment variables.
                     Supports both SQLite and PostgreSQL.
    
    Returns:
        SQLAlchemy engine instance
    """
    if database_url is None:
        # Déterminer le type de base de données depuis les variables d'environnement
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        
        if db_type == "postgresql":
            # Configuration PostgreSQL
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME", "medpost_db")
            db_user = os.getenv("DB_USER", "medpost_user")
            db_password = os.getenv("DB_PASSWORD", "")
            
            database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        else:
            # Configuration SQLite (par défaut)
            database_path = os.getenv("DATABASE_PATH", "rss_qdm.db")
            database_url = f"sqlite:///{database_path}"
    
    # Créer le moteur avec configuration adaptée
    engine_kwargs = {}
    
    if database_url.startswith("postgresql"):
        # Options spécifiques PostgreSQL
        engine_kwargs.update({
            "pool_size": 10,           # Taille du pool de connexions
            "max_overflow": 20,        # Connexions supplémentaires autorisées
            "pool_pre_ping": True,     # Vérifier la connexion avant utilisation
            "pool_recycle": 3600,      # Recycler les connexions après 1h
            "echo": False              # Ne pas logger les requêtes SQL (mettre True pour debug)
        })
    
    engine = create_engine(database_url, **engine_kwargs)
    
    # Créer les tables si elles n'existent pas
    Base.metadata.create_all(engine)
    
    return engine


def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
```

#### Option B : PostgreSQL uniquement (migration complète)

Si vous abandonnez complètement SQLite :

```python
def create_db_and_tables():
    """Create PostgreSQL database engine and tables."""
    # Configuration PostgreSQL depuis les variables d'environnement
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "medpost_db")
    db_user = os.getenv("DB_USER", "medpost_user")
    db_password = os.getenv("DB_PASSWORD")
    
    if not db_password:
        raise ValueError("DB_PASSWORD environment variable must be set")
    
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # Créer le moteur avec pool de connexions
    engine = create_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False
    )
    
    # Créer les tables
    Base.metadata.create_all(engine)
    
    return engine
```

### 3.2 Modifier `fetch_post/main.py`

Mettre à jour l'initialisation de la base de données :

```python
# Remplacer la section d'initialisation de la base de données

# Ancienne version (lignes 1476-1494 environ)
if os.getenv("DOCKER_ENV"):
    database_path = str(script_dir / os.getenv("DATABASE_PATH"))
else:
    script_dir = Path(__file__).resolve().parent
    database_path = str(script_dir.parent / os.getenv("DATABASE_PATH"))

# Nouvelle version
if os.getenv("DB_TYPE", "sqlite").lower() == "postgresql":
    # PostgreSQL : pas besoin de chemin de fichier
    engine = create_db_and_tables()
else:
    # SQLite : utiliser le chemin de fichier
    if os.getenv("DOCKER_ENV"):
        database_path = str(script_dir / os.getenv("DATABASE_PATH"))
    else:
        script_dir = Path(__file__).resolve().parent
        database_path = str(script_dir.parent / os.getenv("DATABASE_PATH"))
    
    engine = create_db_and_tables(f"sqlite:///{database_path}")
```

### 3.3 Modifier `medpost-app/app.py`

```python
# Remplacer la section de configuration de la base de données (lignes 40-62 environ)

# Ancienne version
db_path = str(script_dir / os.getenv("DATABASE_PATH"))
# ...
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

# Nouvelle version
db_type = os.getenv("DB_TYPE", "sqlite").lower()

if db_type == "postgresql":
    # Configuration PostgreSQL
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "medpost_db")
    db_user = os.getenv("DB_USER", "medpost_user")
    db_password = os.getenv("DB_PASSWORD")
    
    if not db_password:
        raise ValueError("DB_PASSWORD must be set for PostgreSQL")
    
    database_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    # Configuration SQLite (défaut)
    if os.getenv("DOCKER_ENV"):
        db_path = str(script_dir / os.getenv("DATABASE_PATH"))
    else:
        db_path = str(script_dir.parent / os.getenv("DATABASE_PATH"))
    
    database_uri = f"sqlite:///{db_path}"

app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
```

---

## Étape 4 : Configuration Docker

### 4.1 Mettre à jour `.env.prod` (medpost-app)

```bash
# Chemins et configuration de base
TZ=Europe/Paris
APP_SECRET_KEY=your-secret-key-here
DOCKER_ENV=true

# Configuration base de données
DB_TYPE=postgresql
DB_HOST=medpost-postgres
DB_PORT=5432
DB_NAME=medpost_db
DB_USER=medpost_user
DB_PASSWORD=your_secure_password_here

# Ancienne config SQLite (conserver pour rollback éventuel)
# DATABASE_PATH=/app/data/rss_qdm.db

# Logs
LOG_PATH=/app/logs/medpost.log
```

### 4.2 Mettre à jour `.env.prod` (fetch_post)

```bash
# Chemins
LOG_PATH=/app/logs/medpost.log
IMAGES_PATH=/app/images/
TZ=Europe/Paris

# Configuration base de données
DB_TYPE=postgresql
DB_HOST=medpost-postgres
DB_PORT=5432
DB_NAME=medpost_db
DB_USER=medpost_user
DB_PASSWORD=your_secure_password_here

# Ancienne config SQLite (conserver pour rollback éventuel)
# DATABASE_PATH=/app/data/rss_qdm.db

# Flux RSS
QDM_URL_RSS=https://www.lequotidiendumedecin.fr/rss.xml
QPH_URL_RSS=https://www.lequotidiendupharmacien.fr/rss.xml

# [Reste de la configuration inchangé]
```

### 4.3 Mettre à jour `medpost-app/docker-compose.yml`

```yaml
version: '3.8'

services:
  # Service PostgreSQL
  postgres:
    image: postgres:16-alpine
    container_name: medpost-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME:-medpost_db}
      POSTGRES_USER: ${DB_USER:-medpost_user}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "${DB_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - medpost-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-medpost_user} -d ${DB_NAME:-medpost_db}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Application Web
  medpost-app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: medpost-app
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - logs_volume:/app/logs
      - images_volume:/app/images
      # Note: data_volume n'est plus nécessaire pour PostgreSQL
    env_file:
      - .env.prod
    networks:
      - medpost-network
    depends_on:
      postgres:
        condition: service_healthy
    command: gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app

  # Service Fetcher
  fetcher-app:
    build:
      context: ../fetch_post
      dockerfile: Dockerfile
    container_name: fetcher-app
    restart: unless-stopped
    volumes:
      - logs_volume:/app/logs
      - images_volume:/app/images
      # Note: data_volume n'est plus nécessaire pour PostgreSQL
    env_file:
      - ../fetch_post/.env.prod
    networks:
      - medpost-network
    depends_on:
      postgres:
        condition: service_healthy
    command: python main.py

volumes:
  postgres_data:
    driver: local
  logs_volume:
    driver: local
  images_volume:
    driver: local
  # data_volume peut être conservé pour rollback SQLite
  # data_volume:
  #   driver: local

networks:
  medpost-network:
    driver: bridge
```

### 4.4 Mettre à jour les Dockerfiles

#### `medpost-app/Dockerfile`

Ajouter psycopg2 :

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Installer les dépendances système pour psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
```

#### `fetch_post/Dockerfile`

Identique, ajouter les dépendances PostgreSQL :

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Installer les dépendances système pour psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

---

## Étape 5 : Migration des données

### 5.1 Exporter les données SQLite

#### Script Python d'export

Créer `scripts/export_sqlite_data.py` :

```python
#!/usr/bin/env python3
"""Export SQLite data to JSON for migration to PostgreSQL"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path


def serialize_datetime(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def export_table(cursor, table_name):
    """Export a table to dictionary format"""
    cursor.execute(f"SELECT * FROM {table_name}")
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    
    data = []
    for row in rows:
        data.append(dict(zip(columns, row)))
    
    return data


def main():
    # Chemin de la base SQLite
    sqlite_db = Path(__file__).parent.parent / "data" / "rss_qdm.db"
    
    if not sqlite_db.exists():
        print(f"❌ Database not found: {sqlite_db}")
        return
    
    # Se connecter à SQLite
    conn = sqlite3.connect(
        str(sqlite_db),
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    cursor = conn.cursor()
    
    # Lister les tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"📊 Found {len(tables)} tables: {', '.join(tables)}")
    
    # Exporter chaque table
    export_data = {}
    for table in tables:
        if table.startswith('sqlite_'):
            continue
        
        print(f"📦 Exporting table: {table}")
        export_data[table] = export_table(cursor, table)
        print(f"   ✓ {len(export_data[table])} rows exported")
    
    # Sauvegarder en JSON
    output_file = Path(__file__).parent.parent / "data" / "sqlite_export.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, default=serialize_datetime, ensure_ascii=False)
    
    print(f"\n✅ Export completed: {output_file}")
    print(f"📊 Total tables exported: {len(export_data)}")
    
    # Statistiques
    for table, data in export_data.items():
        print(f"   - {table}: {len(data)} rows")
    
    conn.close()


if __name__ == "__main__":
    main()
```

#### Exécuter l'export

```bash
# Créer le répertoire scripts si nécessaire
mkdir -p scripts

# Rendre le script exécutable
chmod +x scripts/export_sqlite_data.py

# Exécuter l'export
python scripts/export_sqlite_data.py
```

### 5.2 Option avec pgloader (recommandé pour grands volumes)

#### Installation

```bash
# Ubuntu/Debian
sudo apt-get install pgloader

# macOS
brew install pgloader
```

#### Script de migration

Créer `scripts/migrate_sqlite_to_postgres.load` :

```lisp
LOAD DATABASE
    FROM sqlite://data/rss_qdm.db
    INTO postgresql://medpost_user:your_password@localhost:5432/medpost_db

WITH include drop, create tables, create indexes, reset sequences

SET work_mem to '64MB', maintenance_work_mem to '128MB'

CAST type datetime to timestamptz drop default drop not null using zero-dates-to-null,
     type integer when (= precision 1) to boolean drop typemod

BEFORE LOAD DO
    $$ DROP SCHEMA IF EXISTS public CASCADE; $$,
    $$ CREATE SCHEMA public; $$;
```

#### Exécuter la migration

```bash
# Vérifier que PostgreSQL est accessible
psql -h localhost -U medpost_user -d medpost_db -c "SELECT version();"

# Lancer la migration
pgloader scripts/migrate_sqlite_to_postgres.load

# Vérifier la migration
psql -h localhost -U medpost_user -d medpost_db -c "\dt"
psql -h localhost -U medpost_user -d medpost_db -c "SELECT COUNT(*) FROM articles_rss;"
```

### 5.3 Import manuel des données JSON dans PostgreSQL

Créer `scripts/import_to_postgres.py` :

```python
#!/usr/bin/env python3
"""Import JSON data into PostgreSQL"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Ajouter le chemin parent pour importer les modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetch_post.database import (
    create_db_and_tables, 
    get_session,
    Articles_rss,
    Posts,
    Networks,
    TokensMetadata,
    Base
)


def parse_datetime(value):
    """Parse datetime from various formats"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    
    # Essayer différents formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    
    return None


def import_table(session, table_name, data, model_class):
    """Import data into a specific table"""
    print(f"📥 Importing {len(data)} rows into {table_name}...")
    
    for row in data:
        # Convertir les dates si nécessaire
        for key, value in row.items():
            if isinstance(value, str) and ('date' in key.lower() or key.endswith('_at')):
                row[key] = parse_datetime(value)
        
        # Créer l'objet et l'ajouter à la session
        obj = model_class(**row)
        session.add(obj)
    
    try:
        session.commit()
        print(f"   ✅ {len(data)} rows imported successfully")
    except Exception as e:
        session.rollback()
        print(f"   ❌ Error importing {table_name}: {e}")
        raise


def main():
    # Charger les données JSON
    json_file = Path(__file__).parent.parent / "data" / "sqlite_export.json"
    
    if not json_file.exists():
        print(f"❌ Export file not found: {json_file}")
        print("   Run export_sqlite_data.py first!")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        export_data = json.load(f)
    
    print(f"📊 Loaded {len(export_data)} tables from JSON")
    
    # Configurer PostgreSQL
    os.environ["DB_TYPE"] = "postgresql"
    os.environ["DB_HOST"] = os.getenv("DB_HOST", "localhost")
    os.environ["DB_PORT"] = os.getenv("DB_PORT", "5432")
    os.environ["DB_NAME"] = os.getenv("DB_NAME", "medpost_db")
    os.environ["DB_USER"] = os.getenv("DB_USER", "medpost_user")
    
    if not os.getenv("DB_PASSWORD"):
        print("❌ DB_PASSWORD environment variable must be set")
        return
    
    # Créer les tables et obtenir une session
    print("🔧 Creating tables in PostgreSQL...")
    engine = create_db_and_tables()
    session = get_session(engine)
    
    # Mapping des tables vers les modèles
    table_models = {
        'articles_rss': Articles_rss,
        'posts': Posts,
        'networks': Networks,
        'tokens_metadata': TokensMetadata,
    }
    
    # Ordre d'import (respecter les foreign keys)
    import_order = ['articles_rss', 'networks', 'posts', 'tokens_metadata']
    
    # Importer chaque table
    for table_name in import_order:
        if table_name in export_data and table_name in table_models:
            import_table(session, table_name, export_data[table_name], table_models[table_name])
        else:
            print(f"⚠️  Skipping {table_name} (not found or no model)")
    
    print("\n✅ Import completed successfully!")
    
    # Statistiques finales
    print("\n📊 Final statistics:")
    print(f"   - Articles: {session.query(Articles_rss).count()}")
    print(f"   - Posts: {session.query(Posts).count()}")
    print(f"   - Networks: {session.query(Networks).count()}")
    print(f"   - Tokens: {session.query(TokensMetadata).count()}")
    
    session.close()


if __name__ == "__main__":
    main()
```

#### Exécuter l'import

```bash
# Définir les variables d'environnement
export DB_PASSWORD="your_secure_password"

# Lancer l'import
python scripts/import_to_postgres.py
```

---

## Étape 6 : Tests et validation

### 6.1 Tests de connexion

```bash
# Test de connexion PostgreSQL
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db

# Vérifier les tables
\dt

# Vérifier les données
SELECT COUNT(*) FROM articles_rss;
SELECT COUNT(*) FROM posts;
SELECT COUNT(*) FROM networks;
SELECT COUNT(*) FROM tokens_metadata;

# Vérifier un échantillon d'articles
SELECT id, title, newspaper, pubdate FROM articles_rss ORDER BY pubdate DESC LIMIT 5;

# Quitter psql
\q
```

### 6.2 Lancer l'application

```bash
# Reconstruire les conteneurs avec les nouvelles dépendances
cd medpost-app
docker-compose build --no-cache

# Démarrer les services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f medpost-app
docker-compose logs -f fetcher-app

# Vérifier que PostgreSQL est utilisé
docker-compose logs medpost-app | grep -i postgresql
docker-compose logs medpost-app | grep -i "database connection"
```

### 6.3 Tests fonctionnels

#### Test de l'interface web

```bash
# Ouvrir l'application
open http://localhost:5000

# Ou avec curl
curl http://localhost:5000
```

Vérifier :
- ✅ Connexion à l'application
- ✅ Affichage des articles
- ✅ Création d'une nouvelle publication
- ✅ Programmation d'une publication
- ✅ Upload d'image

#### Test du fetcher

```bash
# Vérifier les logs du fetcher
docker-compose logs fetcher-app | tail -50

# Vérifier la récupération RSS
docker-compose logs fetcher-app | grep -i "RSS"

# Vérifier les publications programmées
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db \
  -c "SELECT id, title, status, date_pub FROM posts ORDER BY date_pub DESC LIMIT 10;"
```

### 6.4 Tests de performance

Créer `scripts/performance_test.py` :

```python
#!/usr/bin/env python3
"""Performance comparison SQLite vs PostgreSQL"""

import time
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fetch_post.database import create_db_and_tables, get_session, Articles_rss


def test_insert_performance(session, count=1000):
    """Test bulk insert performance"""
    print(f"Testing insert of {count} articles...")
    start_time = time.time()
    
    from datetime import datetime
    
    for i in range(count):
        article = Articles_rss(
            nid=i,
            title=f"Test Article {i}",
            link=f"https://example.com/article/{i}",
            summary=f"Summary for article {i}",
            pubdate=datetime.now(),
            online=1,
            newspaper="test"
        )
        session.add(article)
        
        if i % 100 == 0:
            session.commit()
    
    session.commit()
    elapsed = time.time() - start_time
    print(f"✓ Inserted {count} articles in {elapsed:.2f}s ({count/elapsed:.0f} articles/s)")
    
    return elapsed


def test_query_performance(session):
    """Test query performance"""
    print("Testing query performance...")
    start_time = time.time()
    
    # Simple count
    count = session.query(Articles_rss).count()
    
    # Complex query
    recent = session.query(Articles_rss).order_by(
        Articles_rss.pubdate.desc()
    ).limit(100).all()
    
    elapsed = time.time() - start_time
    print(f"✓ Queried {count} articles in {elapsed:.2f}s")
    
    return elapsed


def main():
    # Test PostgreSQL
    print("=" * 50)
    print("PostgreSQL Performance Test")
    print("=" * 50)
    
    os.environ["DB_TYPE"] = "postgresql"
    engine = create_db_and_tables()
    session = get_session(engine)
    
    insert_time_pg = test_insert_performance(session, count=1000)
    query_time_pg = test_query_performance(session)
    
    session.close()
    
    print(f"\n📊 Results:")
    print(f"Insert: {insert_time_pg:.2f}s")
    print(f"Query:  {query_time_pg:.2f}s")


if __name__ == "__main__":
    main()
```

---

## Retour arrière (Rollback)

Si la migration échoue ou rencontre des problèmes :

### Option 1 : Rollback rapide vers SQLite

```bash
# 1. Arrêter les conteneurs
docker-compose down

# 2. Restaurer la configuration SQLite dans .env.prod
# Commenter DB_TYPE=postgresql
# Décommenter DATABASE_PATH=/app/data/rss_qdm.db

# 3. Restaurer le docker-compose.yml original
git checkout docker-compose.yml

# 4. Redémarrer avec SQLite
docker-compose up -d
```

### Option 2 : Restaurer les données depuis la sauvegarde

```bash
# Restaurer le fichier SQLite
cp data/rss_qdm.db.backup data/rss_qdm.db

# Restaurer les volumes Docker
docker run --rm -v data_volume:/target -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/data_volume_backup.tar.gz -C /target
```

---

## Recommandations post-migration

### 1. Monitoring et maintenance

#### Activer les logs PostgreSQL

```sql
-- Se connecter à PostgreSQL
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db

-- Activer le logging des requêtes lentes
ALTER SYSTEM SET log_min_duration_statement = 1000; -- 1 seconde

-- Recharger la configuration
SELECT pg_reload_conf();
```

#### Mettre en place des sauvegardes régulières

Créer `scripts/backup_postgres.sh` :

```bash
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
```

```bash
# Rendre le script exécutable
chmod +x scripts/backup_postgres.sh

# Ajouter une tâche cron (sauvegarde quotidienne à 2h du matin)
crontab -e
# Ajouter cette ligne:
# 0 2 * * * /path/to/medpost/scripts/backup_postgres.sh
```

### 2. Optimisation des performances

#### Créer des index

```sql
-- Se connecter à PostgreSQL
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db

-- Index sur les colonnes fréquemment interrogées
CREATE INDEX idx_articles_rss_nid ON articles_rss(nid);
CREATE INDEX idx_articles_rss_pubdate ON articles_rss(pubdate);
CREATE INDEX idx_articles_rss_newspaper ON articles_rss(newspaper);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_date_pub ON posts(date_pub);
CREATE INDEX idx_posts_network ON posts(network);
CREATE INDEX idx_tokens_metadata_network ON tokens_metadata(network, newspaper);
CREATE INDEX idx_tokens_metadata_expires_at ON tokens_metadata(expires_at);

-- Analyser les tables pour optimiser le query planner
ANALYZE articles_rss;
ANALYZE posts;
ANALYZE networks;
ANALYZE tokens_metadata;
```

#### Configuration PostgreSQL pour production

Éditer `postgres-docker-compose.yml` :

```yaml
services:
  postgres:
    # ... configuration existante ...
    command:
      - "postgres"
      - "-c"
      - "max_connections=200"
      - "-c"
      - "shared_buffers=256MB"
      - "-c"
      - "effective_cache_size=1GB"
      - "-c"
      - "maintenance_work_mem=64MB"
      - "-c"
      - "checkpoint_completion_target=0.9"
      - "-c"
      - "wal_buffers=16MB"
      - "-c"
      - "default_statistics_target=100"
      - "-c"
      - "random_page_cost=1.1"
      - "-c"
      - "effective_io_concurrency=200"
      - "-c"
      - "work_mem=2621kB"
      - "-c"
      - "min_wal_size=1GB"
      - "-c"
      - "max_wal_size=4GB"
```

### 3. Monitoring avec pgAdmin

PgAdmin est déjà configuré dans `postgres-docker-compose.yml`.

Accès :
- URL : http://localhost:5050
- Email : admin@medpost.local
- Mot de passe : (défini dans PGADMIN_PASSWORD)

Configuration du serveur :
1. Clic droit sur "Servers" → "Create" → "Server"
2. Onglet "General" :
   - Name: Medpost
3. Onglet "Connection" :
   - Host: medpost-postgres
   - Port: 5432
   - Database: medpost_db
   - Username: medpost_user
   - Password: [votre mot de passe]

### 4. Sécurité

#### Ne pas exposer PostgreSQL sur l'hôte

Pour la production, retirer le mapping de port :

```yaml
# Dans postgres-docker-compose.yml, commenter ou retirer:
# ports:
#   - "5432:5432"
```

PostgreSQL sera accessible uniquement depuis les conteneurs Docker sur le réseau `medpost-network`.

#### Utiliser des secrets Docker

Pour les mots de passe sensibles :

```bash
# Créer un secret
echo "your_secure_password" | docker secret create postgres_password -

# Utiliser le secret dans docker-compose.yml
services:
  postgres:
    secrets:
      - postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password

secrets:
  postgres_password:
    external: true
```

#### Connexions SSL (optionnel)

Pour sécuriser les connexions :

```sql
-- Générer des certificats SSL
-- Dans le conteneur PostgreSQL
openssl req -new -x509 -days 365 -nodes -text \
  -out /var/lib/postgresql/data/server.crt \
  -keyout /var/lib/postgresql/data/server.key \
  -subj "/CN=medpost-postgres"

chmod 600 /var/lib/postgresql/data/server.key

-- Activer SSL
ALTER SYSTEM SET ssl = on;
SELECT pg_reload_conf();
```

Mettre à jour la connection string :

```python
database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
```

### 5. Alembic pour les migrations futures

Pour gérer les migrations de schéma de manière structurée :

```bash
# Installer Alembic
pip install alembic

# Initialiser Alembic
alembic init alembic

# Configurer alembic.ini avec PostgreSQL URL

# Créer une migration automatique
alembic revision --autogenerate -m "Initial migration"

# Appliquer la migration
alembic upgrade head
```

---

## Checklist finale

### Avant la migration

- [ ] Sauvegarder la base SQLite actuelle
- [ ] Sauvegarder les volumes Docker
- [ ] Tester les scripts de migration sur un environnement de test
- [ ] Planifier une fenêtre de maintenance
- [ ] Informer les utilisateurs de l'interruption de service

### Pendant la migration

- [ ] Arrêter les services Medpost
- [ ] Lancer PostgreSQL
- [ ] Migrer les données (pgloader ou scripts Python)
- [ ] Vérifier l'intégrité des données migrées
- [ ] Mettre à jour le code et la configuration
- [ ] Reconstruire les images Docker

### Après la migration

- [ ] Tester la connexion à PostgreSQL
- [ ] Tester toutes les fonctionnalités de l'application
- [ ] Vérifier les logs pour détecter les erreurs
- [ ] Créer les index de performance
- [ ] Configurer les sauvegardes automatiques
- [ ] Mettre à jour la documentation
- [ ] Surveiller les performances pendant 48h

### En cas de problème

- [ ] Procédure de rollback documentée et testée
- [ ] Sauvegardes accessibles et vérifiées
- [ ] Plan de communication avec les utilisateurs

---

## Ressources supplémentaires

### Documentation officielle

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy PostgreSQL Dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)
- [pgloader Documentation](https://pgloader.readthedocs.io/)

### Outils utiles

- **pgAdmin** : Interface graphique pour PostgreSQL
- **DBeaver** : Client SQL universel
- **pg_dump/pg_restore** : Outils de sauvegarde/restauration
- **pgloader** : Outil de migration de bases de données

### Commandes PostgreSQL utiles

```sql
-- Lister les bases de données
\l

-- Se connecter à une base
\c medpost_db

-- Lister les tables
\dt

-- Décrire une table
\d articles_rss

-- Voir la taille de la base
SELECT pg_size_pretty(pg_database_size('medpost_db'));

-- Voir la taille des tables
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Voir les connexions actives
SELECT * FROM pg_stat_activity;

-- Tuer une connexion
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = 12345;
```

---

## Support et dépannage

### Problèmes courants

#### "FATAL: password authentication failed"

Vérifier :
- Le mot de passe dans `.env.prod`
- Les variables d'environnement PostgreSQL
- La configuration `pg_hba.conf` dans PostgreSQL

```bash
# Réinitialiser le mot de passe
docker exec -it medpost-postgres psql -U postgres
ALTER USER medpost_user WITH PASSWORD 'new_password';
```

#### "could not connect to server: Connection refused"

Vérifier :
- Que PostgreSQL est démarré : `docker ps | grep postgres`
- Le réseau Docker : `docker network inspect medpost-network`
- Le healthcheck : `docker inspect medpost-postgres | grep Health`

#### "relation does not exist"

Les tables n'ont pas été créées :

```bash
# Vérifier les tables
docker exec -it medpost-postgres psql -U medpost_user -d medpost_db -c "\dt"

# Recréer les tables
python -c "from fetch_post.database import create_db_and_tables; create_db_and_tables()"
```

#### Performance dégradée

```sql
-- Analyser les requêtes lentes
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Vérifier les index manquants
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY abs(correlation) DESC;
```

---

## Conclusion

Cette migration de SQLite vers PostgreSQL améliore significativement la robustesse et la scalabilité de l'application Medpost. PostgreSQL offre :

✅ **Meilleure gestion de la concurrence** : Accès simultané par plusieurs services  
✅ **Performances optimisées** : Pour grands volumes de données  
✅ **Intégrité renforcée** : Contraintes et transactions ACID strictes  
✅ **Outils professionnels** : Monitoring, sauvegarde, réplication  
✅ **Évolutivité** : Prêt pour la production et la croissance  

Pour toute question ou problème, consultez la documentation PostgreSQL ou ouvrez une issue sur le dépôt GitHub.

**Bonne migration ! 🚀**
