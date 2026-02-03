# Gestion des Tokens Threads - Documentation

## Vue d'ensemble

Le système de gestion des tokens Threads a été refactorisé pour assurer un renouvellement automatique et sécurisé des tokens d'accès longue durée (60 jours).

## Architecture

### Avant (système legacy)
```
.env (statique) → os.getenv() → Publication
❌ Pas de renouvellement automatique
❌ Token expire tous les 60 jours → intervention manuelle
❌ Pas d'audit trail
```

### Après (nouveau système)
```
.env (seed initial) → DB (TokensMetadata) → Vérification/Renouvellement → Publication
✅ Renouvellement automatique 7 jours avant expiration
✅ Audit trail complet en base de données
✅ Backup de l'ancien token en cas de rollback
✅ Retry strategy avec backoff exponentiel
```

## Nouveau modèle de données

### Table `tokens_metadata`

| Champ              | Type     | Description                                    |
|--------------------|----------|------------------------------------------------|
| id                 | Integer  | Clé primaire                                   |
| network            | String   | Nom du réseau (threads)                        |
| newspaper          | String   | Journal (qdm/qph)                              |
| access_token       | String   | Token d'accès actuel                           |
| expires_at         | DateTime | Date d'expiration du token                     |
| created_at         | DateTime | Date de création de l'entrée                   |
| updated_at         | DateTime | Date de dernière modification                  |
| is_active          | Boolean  | Token actif ou non                             |
| previous_token     | String   | Backup du token précédent (rollback)           |
| last_refresh_date  | DateTime | Date du dernier renouvellement                 |

## Nouveau modèle de données (suite)

### Fonction utilitaire : `get_token_dates(access_token)`

Recherche les dates réelles d'émission et d'expiration d'un token Threads via l'API Meta.

**Usage:**
```python
expires_at, issued_at = get_token_dates(token)
```

**Comportement:**
1. Appelle l'API `/debug_token` de Threads
2. Extrait les timestamps Unix `expires_at` et `issued_at`
3. Convertit les timestamps en objets `datetime` Python
4. **Fallback** : En cas d'erreur API → retourne `now + 60 jours` et `now`

**API Endpoint :**
```
GET https://graph.threads.net/v1.0/debug_token
  ?input_token={TOKEN}
  &access_token={TOKEN}
```

**Réponse attendue:**
```json
{
  "data": {
    "issued_at": 1706000000,
    "expires_at": 1713779200
  }
}
```

## Fonctions implémentées

### 1. `get_threads_token(engine, newspaper)`

Récupère le token depuis la base de données avec fallback vers `.env`.

**Usage:**
```python
token = get_threads_token(engine, "qdm")
```

**Comportement:**
- Recherche le token en DB pour le newspaper spécifié
- Si trouvé → retourne le token de la DB
- Si absent → fallback vers `THREADS_TOKEN_{NEWSPAPER}` dans .env
- Log un warning si le fallback est utilisé (migration recommandée)

### 2. `check_and_refresh_threads_token(engine, newspaper)`

Vérifie l'expiration du token et le renouvelle automatiquement si nécessaire.

**Usage:**
```python
success = check_and_refresh_threads_token(engine, "qdm")
```

**Comportement:**
1. Recherche le token actif en DB pour le journal spécifié
2. Calcule le nombre de jours avant expiration
3. **Si ≥ 7 jours** : log informatif et retour (pas de renouvellement)
4. **Si < 7 jours** : lance le processus de renouvellement
   - Appelle l'API Graph Threads pour renouveler (3 tentatives max)
   - Valide le nouveau token (longueur minimum 50 caractères)
   - Sauvegarde l'ancien token dans `previous_token`
   - Met à jour la DB avec : `access_token`, `expires_at`, `last_refresh_date`, `updated_at`
   - Log le succès avec la nouvelle date d'expiration
5. **En cas d'erreur** :
   - Retry automatique avec backoff exponentiel (1s, 2s, 4s)
   - Log d'erreur HTTP si échec définitif
   - Continue avec l'ancien token
   - Recommande une intervention manuelle

**API Endpoint utilisé:**
```
GET https://graph.threads.net/refresh_access_token
  ?grant_type=th_refresh_token
  &access_token={CURRENT_TOKEN}
```

**Réponse attendue:**
```json
{
  "access_token": "NEW_TOKEN_HERE",
  "token_type": "bearer",
  "expires_in": 5184000
}
```

### 3. `migrate_tokens_to_db(engine)`

Migration one-time pour transférer les tokens du `.env` vers la base de données.

**Usage:**
```python
migrate_tokens_to_db(engine)
```

**Comportement:**
- Idempotent : ne migre que les tokens absents de la DB
- Lit les tokens depuis `THREADS_TOKEN_QDM` et `THREADS_TOKEN_QPH`
- Crée des entrées TokensMetadata avec expiration = now + 60 jours
- Log le nombre de tokens migrés et ignorés

### 4. Modification de `post_all_threads()`

La fonction de publication a été refactorisée pour utiliser la BD :

**Avant:**
```python
def post_all_threads(posts, engine, newspaper, http_session):
    threads_token = os.getenv(f"THREADS_TOKEN_{newspaper.upper()}")
    # ...
```

**Après:**
```python
def post_all_threads(posts, engine, newspaper, http_session):
    # Récupérer le token depuis la DB (avec fallback vers .env)
    threads_token = get_threads_token(engine, newspaper)
    if not threads_token:
        logging.error("THREADS_TOKEN manquant pour %s", newspaper)
        return
    # ... publication
```

**Note:** Le renouvellement des tokens se fait dans `main()` via `check_and_refresh_threads_token()` **avant** chaque cycle de publication, pas dans `post_all_threads()`.

## Workflow de démarrage

### Au premier lancement (migration automatique)

```
1. create_db_and_tables(database_path)
   └─ Crée la table tokens_metadata si elle n'existe pas

2. migrate_tokens_to_db(engine)
   ├─ Lit THREADS_TOKEN_QDM depuis .env
   ├─ Appelle get_token_dates(THREADS_TOKEN_QDM)
   │  └─ Récupère les vraies dates d'émission/expiration via API
   ├─ Lit THREADS_TOKEN_QPH depuis .env
   ├─ Appelle get_token_dates(THREADS_TOKEN_QPH)
   │  └─ Récupère les vraies dates
   ├─ Crée 2 entrées TokensMetadata en DB
   └─ Log: "Migration terminée - 2 token(s) migré(s), 0 ignoré(s)"

3. check_and_refresh_threads_token(engine, "qdm")
   ├─ Récupère token_metadata depuis DB
   ├─ Calcule days_until_expiration
   └─ Log: "Token Threads qdm expire dans 60 jours" (pas de renouvellement < 7j)

4. load_articles(engine, newspaper, url_newspaper, http_session)
   └─ Récupère et stocke les articles RSS

5. post_auto_function(engine, newspaper, http_session)
   └─ Récupère le token via get_threads_token()
   └─ Publie sur Threads
```

### Aux lancements suivants

```
1. migrate_tokens_to_db(engine)
   └─ Log: "Migration terminée - 0 token(s) migré(s), 2 ignoré(s)"
   (Les tokens existent déjà en DB, idempotent)

2. check_and_refresh_threads_token(engine, "qdm")
   ├─ Si >= 7 jours → Log informatif, continue
   └─ Si < 7 jours → Renouvellement automatique

3. load_articles() et post_auto_function()
   └─ Utilisent le token renouvelé ou l'ancien si renouvellement échoue
```

### Workflow de renouvellement (< 7 jours avant expiration)

```
check_and_refresh_threads_token():
├─ Détecte : "Token expire dans 5 jours"
├─ Log: "Renouvellement du token Threads pour qdm (expire le 2026-03-01)"
├─ Appel API Graph Threads (tentative 1)
│  ├─ Succès → nouveau token reçu
│  ├─ Validation : len(token) >= 50
│  └─ Mise à jour DB:
│     ├─ previous_token = ancien token
│     ├─ access_token = nouveau token
│     ├─ expires_at = now + 60 jours
│     ├─ last_refresh_date = now
│     └─ updated_at = now
└─ Log: "✓ Token Threads renouvelé avec succès pour qdm (expire le 2026-05-01)"
```

## Logs et audit

### Logs de succès

```
DEBUG - Token Threads récupéré depuis DB pour qdm (expire: 2026-03-15)
INFO - Token Threads qdm expire dans 45 jours
INFO - Migration terminée - 2 token(s) migré(s), 0 ignoré(s)
DEBUG - Token trouvé dans .env : THAA8gRy88Lk...
DEBUG - Dates renvoyés par l'API converties Iss/Exp: 2026-01-01 12:00:00/2026-03-01 12:00:00
INFO - Token Threads migré pour qdm (expire: 2026-03-01)
INFO - ✓ Token Threads renouvelé avec succès pour qdm (expire le 2026-05-01)
```

### Logs d'avertissement

```
WARNING - Token Threads lu depuis .env pour qdm (migration vers DB recommandée)
WARNING - Aucun token Threads en DB pour qdm - vérification ignorée
WARNING - Aucun token Threads trouvé dans .env pour qdm
WARNING - Utilisation dates par défaut suite à erreur API
```

### Logs d'erreur

```
ERROR - Token Threads introuvable pour qdm
ERROR - THREADS_TOKEN manquant pour qdm
ERROR - Erreur DB lors de la lecture du token Threads: ...
ERROR - Erreur inattendue lors de la lecture du token: ...
ERROR - Erreur HTTP lors du renouvellement (tentative 1/3): 429 Too Many Requests
ERROR - Réponse API invalide (pas de access_token): {...}
ERROR - Token reçu invalide (trop court): THAA8gRy...
ERROR - ✗ ÉCHEC du renouvellement du token Threads pour qdm après 3 tentatives
ERROR - ⚠ ALERTE: Utilisation de l'ancien token - intervention manuelle recommandée
```

## Sécurité

### ✅ Mesures implémentées

1. **Jamais de tokens en clair dans les logs**
   - Seuls les 8 premiers caractères sont loggés si nécessaire
   - Format : `Token: THAA8gRy...` (au lieu du token complet)

2. **Rotation automatique**
   - Renouvellement 7 jours avant expiration (pas le dernier jour)
   - Grace period de 7 jours pour éviter les expirations

3. **Backup et rollback**
   - `previous_token` conservé pendant 60 jours
   - Possibilité de rollback manuel en cas de problème

4. **Retry strategy**
   - 3 tentatives avec backoff exponentiel
   - Gestion des erreurs HTTP (429, 5xx)
   - Continuation avec l'ancien token en cas d'échec total

5. **Audit trail**
   - `created_at`, `updated_at`, `last_refresh_date` tracent tous les changements
   - Historique des renouvellements dans les logs

### ⚠️ Recommandations additionnelles (optionnel)

1. **Chiffrement au repos**
   ```python
   from cryptography.fernet import Fernet

   # Chiffrer avant stockage
   cipher = Fernet(ENCRYPTION_KEY)
   encrypted_token = cipher.encrypt(token.encode())

   # Déchiffrer à la lecture
   decrypted_token = cipher.decrypt(encrypted_token).decode()
   ```

2. **Docker Secrets** (production)
   - Utiliser `docker secret create` au lieu de .env
   - Monter les secrets dans `/run/secrets/`

3. **Permissions fichiers**
   ```bash
   chmod 600 .env.dev
   chmod 600 .env.prod
   ```

4. **Alerting externe**
   - Envoyer un email/webhook si le renouvellement échoue
   - Monitoring de la date d'expiration

## Migration depuis l'ancien système

### Étape 1 : Déployer le nouveau code

```bash
git pull origin claude
cd medpost-app
docker compose build
```

### Étape 2 : Premier démarrage

```bash
docker compose up -d
docker logs fetcher
```

**Logs attendus:**
```
INFO - Migration terminée - 2 token(s) migré(s), 0 ignoré(s)
INFO - Token Threads récupéré depuis DB pour qdm (expire: 2026-03-15)
INFO - Token Threads qdm expire dans 60 jours
```

### Étape 3 : Vérifier la base de données

```bash
docker exec -it sqlite-cli sqlite3 /data/rss_qdm.db
```

```sql
SELECT network, newspaper,
       substr(access_token, 1, 12) || '...' as token_preview,
       expires_at, is_active
FROM tokens_metadata;
```

**Résultat attendu:**
```
threads|qdm|THAA8gRy88Lk...|2026-03-15 10:30:00|1
threads|qph|THAA8gRy88Lk...|2026-03-15 10:30:00|1
```

### Étape 4 : Tester le renouvellement (optionnel)

Pour forcer un test du renouvellement :

```sql
-- Mettre la date d'expiration à dans 5 jours
UPDATE tokens_metadata
SET expires_at = datetime('now', '+5 days')
WHERE newspaper = 'qdm';
```

Puis relancer le fetcher :
```bash
docker restart fetcher
docker logs -f fetcher
```

**Logs attendus:**
```
INFO - Token Threads qdm expire dans 5 jours
INFO - Renouvellement du token Threads pour qdm (expire le 2026-02-06)
INFO - ✓ Token Threads renouvelé avec succès pour qdm (expire le 2026-04-07)
```

## Maintenance

### Vérifier l'état des tokens

```sql
SELECT
    network,
    newspaper,
    datetime(expires_at) as expires_at,
    CAST((julianday(expires_at) - julianday('now')) AS INTEGER) as days_remaining,
    datetime(last_refresh_date) as last_refresh,
    is_active
FROM tokens_metadata
ORDER BY newspaper;
```

### Renouveler manuellement un token

Si besoin de forcer un renouvellement manuel :

1. Obtenir un nouveau token depuis Meta Business (https://developers.facebook.com/apps/)
2. Mettre à jour en DB :

```sql
UPDATE tokens_metadata
SET access_token = 'NOUVEAU_TOKEN_ICI',
    expires_at = datetime('now', '+60 days'),
    updated_at = datetime('now'),
    previous_token = access_token,
    last_refresh_date = datetime('now')
WHERE network = 'threads' AND newspaper = 'qdm';
```

### Désactiver un token

```sql
UPDATE tokens_metadata
SET is_active = 0
WHERE network = 'threads' AND newspaper = 'qdm';
```

Le système passera automatiquement au fallback `.env`.

## Troubleshooting

### Le token n'est pas renouvelé automatiquement

**Symptôme:** Logs indiquent "Token expire dans 3 jours" mais pas de renouvellement

**Causes possibles:**
1. Le seuil de 7 jours n'est pas atteint → normal
2. L'API Graph retourne une erreur → vérifier les logs d'erreur
3. Le token en DB est invalide → vérifier `is_active`

**Solution:**
```bash
docker logs fetcher | grep -i "threads"
docker logs fetcher | grep -i "renouvellement"
```

### Erreur "THREADS_TOKEN manquant"

**Symptôme:** `ERROR - THREADS_TOKEN manquant pour qdm`

**Causes:**
- Pas de token en DB ET pas de token dans .env

**Solution:**
```bash
# Vérifier .env
cat .env.dev | grep THREADS_TOKEN_QDM

# Vérifier DB
docker exec -it sqlite-cli sqlite3 /data/rss_qdm.db "SELECT * FROM tokens_metadata;"
```

### API Graph retourne 400/401

**Symptôme:** `ERROR - Erreur HTTP lors du renouvellement: 401 Unauthorized`

**Causes:**
- Token expiré ou révoqué
- Mauvais format de requête

**Solution:**
1. Régénérer un nouveau token depuis Meta Business
2. Le mettre dans .env
3. Supprimer l'entrée en DB pour forcer la re-migration

```sql
DELETE FROM tokens_metadata WHERE newspaper = 'qdm';
```

4. Redémarrer le fetcher

## Références

- [Threads API Documentation](https://developers.facebook.com/docs/threads)
- [Long-lived Access Tokens](https://developers.facebook.com/docs/threads/get-started/get-access-tokens-and-permissions#long-lived-tokens)
- [Token Refresh](https://developers.facebook.com/docs/threads/get-started/get-access-tokens-and-permissions#refresh-tokens)
