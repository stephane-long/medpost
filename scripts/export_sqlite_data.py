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
