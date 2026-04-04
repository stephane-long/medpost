# Package Partagé Medpost

Ce package contient les modules communs aux services `rss-fetcher` et `social-publisher`.

## Contenu

### database.py

Module contenant les modèles de base de données SQLAlchemy et les fonctions utilitaires.

#### Modèles

- **Articles_rss** : Articles récupérés depuis les flux RSS
- **Posts** : Publications planifiées ou publiées sur les réseaux sociaux
- **Networks** : Configuration des réseaux sociaux
- **TokensMetadata** : Gestion des tokens d'accès (notamment Threads)
- **User** : Utilisateurs de l'application web

#### Fonctions

- **create_db_and_tables(engine: Engine)** : Crée la base de données et toutes les tables
- **get_session() -> Session** : Retourne une session SQLAlchemy configurée

## Installation

Le package est installé automatiquement lors du build Docker :

```dockerfile
COPY setup.py /shared/setup.py
COPY shared /shared/shared
RUN pip install --no-cache-dir /shared
```

## Utilisation

### Dans rss-fetcher

```python
from shared.database import (
    Articles_rss,
    create_db_and_tables,
    get_session,
)
```

### Dans social-publisher

```python
from shared.database import (
    Articles_rss,
    Posts,
    Networks,
    TokensMetadata,
    create_db_and_tables,
    get_session,
)
```

## Développement local

Pour utiliser le package en développement local :

```bash
cd fetch_post
pip install -e .
```

L'option `-e` permet une installation en mode "editable", où les modifications du code sont immédiatement prises en compte sans réinstallation.

## Versioning

La version actuelle est `1.0.0` (définie dans `setup.py`).

Pour mettre à jour la version :

1. Modifier le numéro de version dans `setup.py`
2. Rebuilder les images Docker pour appliquer les changements

## Avantages de cette architecture

- ✅ **Une seule source de vérité** : Le code de database.py n'existe qu'à un seul endroit
- ✅ **Versioning** : Le package peut être versionné indépendamment
- ✅ **Testable** : Peut être testé indépendamment des services
- ✅ **Maintenabilité** : Modifications faciles et propagées automatiquement
- ✅ **Compatible Docker** : Pas de problèmes avec les liens symboliques
- ✅ **Standard Python** : Respecte les conventions de packaging Python
