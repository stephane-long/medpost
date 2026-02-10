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
