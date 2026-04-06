# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Medpost is a Flask-based social media automation platform for managing and scheduling posts to multiple social networks (X/Twitter, Bluesky, Threads) for French medical journals (Le Quotidien du Médecin and Le Quotidien du Pharmacien). The system consists of two main components:

1. **medpost-app**: Flask web application for managing posts, articles, and user authentication
2. **fetch_post**: Background service for RSS feed retrieval and automated post publishing

## Architecture

### Docker Services (medpost-app/docker-compose.yml)

The application runs as three Docker containers sharing data via Docker volumes:

- **medpost-app** (container: `medpost`): Flask web UI for creating, editing, and scheduling posts
- **rss-fetcher** (container: `rss-fetcher`): RSS feed ingestion — runs `rss_fetcher/main.py`
- **social-publisher** (container: `social-publisher`): Social media publishing — runs `social_publisher/main.py`
- **sqlite-cli** (Utility): Alpine container for direct database access

### Shared Resources (Docker Volumes)

- `data_volume`: SQLite database (`rss_qdm.db`)
- `logs_volume`: Application logs (`medpost.log`)
- `images_volume`: Post images and default placeholder

### Database Schema

The application uses SQLAlchemy with SQLite. Key models:

- **Articles_rss**: RSS feed articles with metadata (title, link, summary, image_url, pubdate, nid, newspaper)
- **Posts**: Scheduled/published posts with status tracking (plan/pub), linked to articles and networks
- **Networks**: Social media platforms with custom tags (X, Bluesky, Threads)
- **User**: Authentication with admin flag (Flask-Login)

**Critical**: The `nid` field in Articles_rss is the Drupal node ID from the source website. It's used to identify and deduplicate articles.

### Environment Configuration

Each service has its own `.env` file (`medpost-app/.env.dev` and `fetch_post/.env.dev`). The `.env.dev` files default to Docker mode (`DOCKER_ENV=1` uncommented). For local development without Docker, swap the commented sections in each file:

```bash
# Comment out DOCKER section, uncomment LOCAL section:
# DOCKER_ENV=1  ← comment this
# DATABASE_PATH=data/rss_qdm.db  ← swap this with the local path variant
```

Environment detection via `DOCKER_ENV` variable determines path resolution (script_dir vs script_dir.parent).

## Common Development Commands

### Docker Development

```bash
# Build and start all services (from medpost-app directory)
cd medpost-app
docker compose up --build -d

# View logs
docker logs medpost
docker logs rss-fetcher
docker logs social-publisher

# Stop services
docker compose down

# Access SQLite database directly
docker exec -it sqlite-cli sqlite3 /data/rss_qdm.db
```

### Local Development (without Docker)

```bash
# Create/activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Flask app (from medpost-app directory)
cd medpost-app
python app.py  # Runs on port 8000

# Run RSS fetcher manually (from fetch_post directory)
cd fetch_post
python -m rss_fetcher.main

# Run social publisher manually
python -m social_publisher.main
```

### Database Operations

```bash
# Access database via Docker
docker exec -it sqlite-cli sh
sqlite3 /data/rss_qdm.db

# Common queries
SELECT * FROM networks;
SELECT * FROM posts WHERE status='plan' ORDER BY date_pub;
SELECT COUNT(*) FROM articles_rss WHERE newspaper='qdm';
```

## Key Implementation Details

### Image Processing

The application implements custom image handling in `app.py`:

- `clean_and_resize_image()`: Strips metadata and compresses images to meet platform requirements (max 500KB for X, 1MB for Bluesky)
- `save_image()`: Processes uploaded images and saves to `static/images/`
- Default fallback: `images/no_picture.jpg` for missing images

### Fetcher Service Architecture (fetch_post/)

The fetcher is split into two independent services, each running in its own Docker container:

**Module Organization**:
- `rss_fetcher/main.py`: RSS feed processing and article import (runs as `rss-fetcher` container)
- `social_publisher/main.py`: Social media publication (runs as `social-publisher` container)
- `shared/database.py`: Shared SQLAlchemy models (Articles_rss, Posts, Networks, TokensMetadata)
- `setup.py`: Package setup for the `shared` module (installed in both containers)

**Key Functions**:
- **RSS Fetching**: `load_articles()` retrieves feeds, validates articles, extracts metadata, stores in database
- **Social Publishing**: `post_auto_function()` publishes queued posts across networks
- **Token Management**: `get_threads_token()`, `check_and_refresh_threads_token()`, `migrate_tokens_to_db()` handle Threads token lifecycle

### Social Media Publishing Implementation

Each platform has distinct requirements:

**X (Twitter)**:
- Requires OAuth1 authentication with 4 credentials
- Image upload via separate media endpoint, returns media_id
- Posts can include media_ids or link cards

**Bluesky**:
- Uses atproto SDK with login/password
- Creates embedded cards with thumb images for links
- Direct image posts for non-link content
- Images downloaded from URLs or loaded from local files

**Threads**:
- Two-step process: create media container, then publish
- Local images must be uploaded to external bucket (SFTP) before posting
- Requires permalink retrieval after posting for URL storage
- Images automatically deleted from bucket after successful post

### Article Import Workflow

1. User pastes article URL in web UI (`/import` route)
2. System fetches HTML and extracts Twitter card metadata (title, description, image)
3. Extracts Drupal `nid` from `data-history-node-id` attribute
4. Checks if article exists in database by NID
5. Creates new article or returns existing one
6. User can then create scheduled posts for different networks

### Status Flow

Articles and posts follow this lifecycle:

1. **Article**: RSS import or manual URL import → `online=1` (visible) or `online=0` (hidden/deleted)
2. **Post**: Created with `status='plan'` → Published to network → `status='pub'` + `network_post_id` stored

### Authentication

Flask-Login with hashed passwords (Werkzeug). Admin users can manage users via `/admin` route. Session lifetime: 12 hours.

## Critical Configuration Notes

### Path Resolution Logic

**Flask app (medpost-app/app.py)**:
```python
if os.getenv("DOCKER_ENV"):
    db_path = str(script_dir / os.getenv("DATABASE_PATH"))
else:
    db_path = str(script_dir.parent / os.getenv("DATABASE_PATH"))
```

**Fetcher modules (fetch_post/rss_fetcher/main.py, fetch_post/social_publisher/main.py)**:
```python
if os.getenv("DOCKER_ENV"):
    db_path = str(script_dir / os.getenv("DATABASE_PATH"))
else:
    # Note: script_dir.parent.parent accounts for module depth (rss_fetcher/ or social_publisher/)
    db_path = str(script_dir.parent.parent / os.getenv("DATABASE_PATH"))
```

The extra `.parent` in fetcher modules is necessary because:
- `rss_fetcher/main.py` is one level deeper than the root
- `social_publisher/main.py` is also one level deeper than the root
- Path resolution must account for this additional directory depth

### Network Tags

Each social network can have custom UTM tags or tracking parameters stored in the Networks table. These are appended to article URLs when posting. Managed via `/tags` route.

### RSS Feed Processing

The fetcher processes up to 25 articles per feed run with:
- Configurable crawl delay between requests (default 1.5s)
- Automatic retry logic with exponential backoff
- Rate limit handling (429 responses)
- Article validation to skip unwanted content (e.g., "Votre journal au format numérique")

### Shared Database Module (fetch_post/shared/database.py)

All SQLAlchemy models are centralized in `shared/database.py`:
- **Articles_rss**: RSS articles with NID, newspaper, metadata
- **Posts**: Scheduled/published posts with status tracking
- **Networks**: Social media platforms with tags
- **TokensMetadata**: Threads token management with expiration tracking

This module is imported by both `rss_fetcher/main.py` and `social_publisher/main.py` to ensure consistency.

### Dual Newspaper Support

The system handles two newspapers (qdm/qph) with separate:
- Social media credentials (suffixed with `_QDM` or `_QPH`)
- RSS feed URLs
- Post scheduling

All database operations filter by the `newspaper` field to maintain separation.

## Production Deployment Notes

### Volume Initialization

External volumes must be created and populated before first run:

```bash
# Create database volume and copy initial DB
docker run --rm -v data_volume:/data -v /host/path/data:/host alpine cp /host/rss_qdm.db /data/

# Create logs volume and copy initial log file
docker run --rm -v logs_volume:/data -v /host/path/logs:/host alpine cp /host/medpost.log /data/

# Create images volume and copy default image
docker run --rm -v images_volume:/data -v /host/path/images:/host alpine cp /host/no_picture.jpg /data/
```

### Docker Compose Configuration

For production, modify `docker-compose.yml`:
- Change `env_file` to `.env.prod`
- Comment out development volume mounts (`.:/app`)
- Ensure external volumes are declared

### Scheduled Publishing

The fetcher containers should be run periodically (cron/scheduler) rather than continuously:

```bash
# Example cron jobs to run every 2 hours
0 */2 * * * docker start rss-fetcher
0 */2 * * * docker start social-publisher
```

## Technology Stack

- **Backend**: Flask 3.1.0 with Flask-Login, Flask-SQLAlchemy
- **Database**: SQLite 3 with SQLAlchemy ORM
- **Social Media APIs**:
  - Tweepy 4.15.0 (X/Twitter API v2)
  - atproto 0.0.59 (Bluesky)
  - Meta Graph API (Threads)
- **HTTP**: Requests with retry strategy and connection pooling
- **HTML Parsing**: BeautifulSoup4
- **RSS**: feedparser
- **Image Processing**: Pillow
- **Deployment**: Docker with Gunicorn (4 workers)

## Common Troubleshooting

- **Import fails**: Check that article has Twitter card metadata and data-history-node-id attribute
- **Image upload fails**: Verify image is under size limits, check file permissions in static/images/
- **Posts not publishing**: Check date_pub is in the past, status is 'plan', verify API credentials
- **Database locked**: Ensure only one process writes to SQLite at a time, check volume permissions
- **Threads posts fail**: Verify bucket SFTP credentials, check image URL accessibility
