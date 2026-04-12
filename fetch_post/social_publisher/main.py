"""Service Social Publisher - Publication des posts sur les réseaux sociaux"""

import logging
import os
import platform
import re
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
import tweepy
from atproto import Client, models
from requests.adapters import HTTPAdapter
from requests_oauthlib import OAuth1
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from urllib3.util.retry import Retry

# Import des modèles de la base de données
from shared.database import (
    Articles_rss,
    Posts,
    Networks,
    TokensMetadata,
    create_db_and_tables,
    get_session,
)

# ============================================
# CONFIG
# ============================================

script_dir = Path(__file__).parent
image_path = None

# ============================================
# SESSION HTTP
# ============================================


def create_http_session() -> requests.Session:
    """
    Crée une session HTTP réutilisable configurée pour le scraping

    Returns:
        requests.Session: Session HTTP configurée et prête à l'emploi
    """
    session = requests.Session()

    # ============================================
    # 1. CONSTRUCTION DU USER-AGENT
    # ============================================

    # Informations du bot depuis variables d'environnement (avec valeurs par défaut)
    bot_name = os.getenv("BOT_NAME", "MedpostBot")
    bot_version = os.getenv("BOT_VERSION", "1.0")
    bot_contact = os.getenv("BOT_CONTACT", "agenthttp.recognize312@passmail.net")

    # Construction du User-Agent
    # Format: NomBot/Version (+URL; email) Client/Version Système
    user_agent = (
        f"{bot_name}/{bot_version} "
        f"({bot_contact}) "
        f"Python-requests/{requests.__version__} "
        f"{platform.system()}/{platform.release()}"
    )

    # ============================================
    # 2. CONFIGURATION DES HEADERS
    # ============================================

    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }
    )

    # ============================================
    # 3. CONFIGURATION DU RETRY AUTOMATIQUE
    # ============================================

    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "HEAD"],
        raise_on_status=False,
    )

    # ============================================
    # 4. CONFIGURATION DU CONNECTION POOLING
    # ============================================

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=5,
        pool_maxsize=10,
        pool_block=False,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    logging.info("Session HTTP créée - User-Agent: %s", user_agent)
    logging.debug("Headers configurés: %s", dict(session.headers))

    return session


# ============================================
# FONCTIONS DE PUBLICATIONS
# ============================================


def fetch_posts(engine: Engine, selectedfeed: str, newspaper: str) -> Sequence[Any]:
    with get_session(engine) as session:
        statement = (
            select(
                Posts.title,
                Posts.description,
                Posts.tagline,
                Posts.image_url,
                Articles_rss.id.label("article_id"),
                Articles_rss.link,
                Articles_rss.image_url.label("article_image_url"),
                Networks.name.label("network_name"),
                Posts.id.label("post_id"),
            )
            .join(Articles_rss, Articles_rss.id == Posts.id_article)
            .join(Networks, Networks.id == Posts.network)
            .where(Networks.name == selectedfeed)
            .where(Posts.status == "plan")
            .where(Posts.date_pub < datetime.today())
            .where(Articles_rss.newspaper == newspaper)
        )
        try:
            posts = session.execute(statement).mappings().all()
            logging.info("Lecture de %s posts sur %s", len(posts), selectedfeed)
            logging.debug("POST LUS : %s", posts)
        except Exception as e:
            logging.error("Erreur de lecture des posts : %s", e)
    return posts


def update_network_post_id(engine: Engine, post_id: int, network_post_id: str) -> None:
    """
    Met à jour l'URL (avec Id fourni par le réseau) du post dans la base de données.

    Args:
        engine: L'objet moteur SQLAlchemy.
        post_id (int): L'ID du post à mettre à jour.
        network_post_id (str): L'ID du post sur le réseau social (URL avec id)
    """
    with get_session(engine) as session:
        try:
            statement = (
                update(Posts)
                .where(Posts.id == post_id)
                .values(network_post_id=network_post_id)
            )
            session.execute(statement)
            session.commit()
            logging.debug("Transaction committée avec succès post ID: %s", post_id)
        except SQLAlchemyError as e:
            session.rollback()
            logging.error(
                "Erreur lors de la MAJ du network_post_id du post %s: %s", post_id, e
            )
        except Exception as e:
            session.rollback()
            logging.error(
                "Erreur inattendue lors de la MAJ du network_post_id pour le post %s: %s",
                post_id,
                e,
            )


def modify_status(engine: Engine, post_id: int, post_title: str) -> None:
    with get_session(engine) as session:
        try:
            statement = update(Posts).where(Posts.id == post_id).values(status="pub")
            session.execute(statement)
            session.commit()
            logging.info("Mise à jour du statut de publication de %s", post_title)
        except Exception as e:
            logging.error(
                "Erreur %s lors de modification du status post %s", e, post_title
            )


def get_network_tag(engine: Engine, network: str) -> Optional[str]:
    try:
        with get_session(engine) as session:
            tag = session.scalar(select(Networks.tag).where(Networks.name == network))
            return tag
    except Exception as err:
        logging.error("Impossible d'accéder au tag de %s : Erreur %s", network, err)
        return None


# ===== X =====


def connect_x_apiv2(
    x_api_key: str, x_api_secret: str, x_access_token: str, x_access_token_secret: str
) -> tweepy.Client:
    return tweepy.Client(
        consumer_key=x_api_key,
        consumer_secret=x_api_secret,
        access_token=x_access_token,
        access_token_secret=x_access_token_secret,
    )


def post_to_x(
    api: tweepy.Client, post: dict[str, Any], tag: str, media_id: list[int]
) -> tuple[bool, Optional[str]]:
    if post["link"] != "":
        url_to_post = post["link"] + tag
    else:
        url_to_post = ""
    post_content = f"{post['title']} {url_to_post}"
    try:
        if media_id == []:
            response = api.create_tweet(text=post_content)
        else:
            response = api.create_tweet(text=post_content, media_ids=media_id)
        network_post_id = response.data["id"]
        logging.info(
            "Tweet publié - ID : %s Link : %s - media : %s",
            network_post_id,
            url_to_post,
            media_id,
        )
        return True, network_post_id
    except Exception as e:
        logging.error("Échec du post: %s\n%s", e, post_content)
        return False, None


def upload_image_to_x(
    http_session: requests.Session,
    x_api_key: str,
    x_api_secret: str,
    x_access_token: str,
    x_access_token_secret: str,
    image_file: str,
) -> Optional[int]:
    image_file = f"{image_path}/{image_file}"
    auth = OAuth1(x_api_key, x_api_secret, x_access_token, x_access_token_secret)
    upload_url = "https://upload.twitter.com/1.1/media/upload.json"
    with open(image_file, "rb") as image_file:
        files = {"media": image_file}
        try:
            req = http_session.post(url=upload_url, auth=auth, files=files)
            req.raise_for_status()
            media_id = req.json()["media_id"]
            return media_id
        except requests.exceptions.HTTPError as e:
            logging.error(
                "Erreur HTTP lors de l'upload de l'image sur X: %s - Réponse: %s",
                e,
                req.text,
            )
            return None
        except Exception as e:
            logging.error("Erreur upload : %s", e)
            return None


def post_all_x(
    posts: Sequence[Any], engine: Engine, newspaper: str, http_session: requests.Session
) -> None:
    x_api_secret = os.getenv(f"API_KEY_SECRET_{newspaper.upper()}")
    x_api_key = os.getenv(f"API_KEY_{newspaper.upper()}")
    x_access_token = os.getenv(f"ACCESS_TOKEN_{newspaper.upper()}")
    x_access_token_secret = os.getenv(f"ACCESS_TOKEN_SECRET_{newspaper.upper()}")
    x_url = os.getenv(f"X_URL_{newspaper.upper()}")
    # Connexion à X API V2
    try:
        x_apiv2 = connect_x_apiv2(
            x_api_key, x_api_secret, x_access_token, x_access_token_secret
        )
    except Exception as e:
        logging.error("Erreur de connexion à l'API V2 de X: %s", e)
        return
    tag = get_network_tag(engine, "X")

    for post in posts:
        # Article ayant une image donc inutile d'uploader une image
        post_image = post["image_url"]
        if re.search("^https?", post_image):
            media_id = []  # Pas besoin d'uploader une image
            success, network_post_id = post_to_x(x_apiv2, post, tag, media_id)
        # Article sans image, post avec image uploadée
        elif post_image != "":
            retour_id = upload_image_to_x(
                http_session,
                x_api_key,
                x_api_secret,
                x_access_token,
                x_access_token_secret,
                post_image,
            )
            if retour_id:
                media_id = [retour_id]
            else:
                media_id = []  # Upload échoué, on poste sans image
                logging.error("Upload image échoué pour: %s", post["title"])

            success, network_post_id = post_to_x(x_apiv2, post, tag, media_id)
        else:
            success = False
            network_post_id = None

        # Si post publié, changement de statut dans la base plan -> pub
        if success:
            modify_status(engine, post["post_id"], post["title"])
            network_post_link = x_url + network_post_id
            update_network_post_id(engine, post["post_id"], network_post_link)
        else:
            logging.error("Changement de statut impossible %s", post["title"])


# ===== Bluesky =====


def post_to_bluesky(post, client_bluesky, tag: str, http_session):
    post_image = post["image_url"]
    if post_image and re.search("^https?://", post_image):
        logging.debug("Image URL : %s", post_image)
        # Récupération de l'image en ligne
        try:
            response = http_session.get(post_image, timeout=10)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type")
            if content_type not in ["image/jpeg", "image/png"]:
                logging.error(
                    "Erreur : Le type de contenu attendu est"
                    " 'image/jpeg' ou 'image/png', mais reçu %s",
                    content_type,
                )
                return None
            img_data = response.content
            logging.debug("Upload de l'image Bluesky OK %s", post["title"])
        except requests.exceptions.HTTPError as err:
            logging.error("Erreur HTTP lors de la lecture de l'image BSky : %s", err)
            return None
    else:
        # Récupération de l'image en local
        image_file = f"{image_path}/{post_image}"

        try:
            with open(image_file, "rb") as image_file:
                img_data = image_file.read()
        except Exception as e:
            logging.error("Erreur lors du load de l'image %s : %s", post_image, e)
            return None

    if post["link"] != "":
        # Création et upload d'une WebSite Card
        thumb = client_bluesky.upload_blob(img_data)
        url_to_post = post["link"] + tag
        logging.info("URL Bluesky : %s", url_to_post)
        embed = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=post["title"],
                description=post["description"],
                uri=url_to_post,
                thumb=thumb.blob,
            )
        )
        try:
            response = client_bluesky.send_post(post["tagline"], embed=embed)
            network_post_id = response.uri.rsplit("/", 1)[1]
            logging.info(
                "Post %s posté sur Bluesky  URI = %s", post["title"], network_post_id
            )
            return network_post_id
        except Exception as err:
            logging.error(
                "Échec de publication sur Bluesky de %s - %s", post["title"], err
            )
            return None
    else:
        # Upload d'un post créé avec une image (pas de post['link'])
        try:
            response = client_bluesky.send_image(
                text=post["tagline"], image=img_data, image_alt=""
            )
            network_post_id = response.uri.rsplit("/", 1)[1]
            logging.info(
                "Post posté sur Bluesky : %s, %s", post["tagline"], network_post_id
            )
            return network_post_id
        except Exception as err:
            logging.error(
                "Échec de publication sur Bluesky de %s - %s", post["tagline"], err
            )
            return None


def post_all_bluesky(posts, engine, newspaper: str, http_session) -> None:
    bluesky_login = os.getenv(f"BLUESKY_LOGIN_{newspaper.upper()}")
    bluesky_password = os.getenv(f"BLUESKY_PASSWORD_{newspaper.upper()}")
    bluesky_url = os.getenv(f"BLUESKY_URL_{newspaper.upper()}")
    tag = get_network_tag(engine, "Bluesky")
    client_bluesky = Client()
    try:
        client_bluesky.login(bluesky_login, bluesky_password)
        logging.debug("Connexion réussie à Bluesky")
    except Exception as err:
        logging.error("Échec de connexion à Bluesky %s", err)
        return
    tag = get_network_tag(engine, "Bluesky")
    for post in posts:
        network_post_id = post_to_bluesky(post, client_bluesky, tag, http_session)
        if network_post_id is not None:
            network_post_link = bluesky_url + str(network_post_id)
            update_network_post_id(engine, post["post_id"], network_post_link)
            modify_status(engine, post["post_id"], post["tagline"])


# ===== Threads =====


def get_threads_token(engine: Engine, newspaper: str) -> Optional[str]:
    """
    Récupère le token Threads depuis la base de données.
    Utilise le .env comme fallback si le token n'existe pas en DB.

    Args:
        engine: Moteur SQLAlchemy
        newspaper: Nom du journal (qdm/qph)

    Returns:
        str | None: Le token d'accès ou None si non trouvé
    """
    try:
        with get_session(engine) as session:
            token_metadata = session.execute(
                select(TokensMetadata)
                .where(TokensMetadata.network == "threads")
                .where(TokensMetadata.newspaper == newspaper)
                .where(TokensMetadata.is_active)
            ).scalar_one_or_none()

            if token_metadata:
                logging.debug(
                    "Token Threads récupéré depuis DB pour %s (expire: %s)",
                    newspaper,
                    token_metadata.expires_at,
                )
                return token_metadata.access_token
            else:
                # Fallback vers .env si pas en DB
                token = os.getenv(f"THREADS_TOKEN_{newspaper.upper()}")
                if token:
                    logging.warning(
                        "Token Threads lu depuis .env pour %s (migration vers DB recommandée)",
                        newspaper,
                    )
                else:
                    logging.error("Token Threads introuvable pour %s", newspaper)
                return token

    except SQLAlchemyError as err:
        logging.error("Erreur DB lors de la lecture du token Threads: %s", err)
        # Fallback vers .env en cas d'erreur DB
        return os.getenv(f"THREADS_TOKEN_{newspaper.upper()}")
    except Exception as err:
        logging.error("Erreur inattendue lors de la lecture du token: %s", err)
        return None


def check_and_refresh_threads_token(engine: Engine, newspaper: str) -> bool:
    """
    Vérifie l'expiration du token Threads et le renouvelle si nécessaire.

    Args:
        engine: Moteur SQLAlchemy
        newspaper: Nom du journal (qdm/qph)

    Returns:
        bool: True si le token est valide (ou renouvelé avec succès), False sinon
    """
    try:
        with get_session(engine) as session:
            token_metadata = session.execute(
                select(TokensMetadata)
                .where(TokensMetadata.network == "threads")
                .where(TokensMetadata.newspaper == newspaper)
                .where(TokensMetadata.is_active)
            ).scalar_one_or_none()

            if not token_metadata:
                logging.warning(
                    "Aucun token Threads en DB pour %s - vérification ignorée",
                    newspaper,
                )
                return True  # Pas de token en DB, utilisation du .env

            # Calculer le nombre de jours avant expiration
            now = datetime.now()
            days_until_expiration = (token_metadata.expires_at - now).days

            logging.info(
                "Token Threads %s expire dans %d jours",
                newspaper,
                days_until_expiration,
            )

            # Renouveler si moins de 7 jours avant expiration
            if days_until_expiration < 7:
                logging.info(
                    "Renouvellement du token Threads pour %s (expire le %s)",
                    newspaper,
                    token_metadata.expires_at.strftime("%Y-%m-%d"),
                )

                # Appel API avec retry strategy
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        refresh_url = "https://graph.threads.net/refresh_access_token"
                        params = {
                            "grant_type": "th_refresh_token",
                            "access_token": token_metadata.access_token,
                        }

                        response = requests.get(refresh_url, params=params, timeout=10)
                        response.raise_for_status()

                        data = response.json()
                        new_token = data.get("access_token")
                        expires_in = data.get(
                            "expires_in", 5184000
                        )  # 60 jours par défaut

                        if not new_token:
                            logging.error(
                                "Réponse API invalide (pas de access_token): %s", data
                            )
                            continue

                        # Validation basique du nouveau token
                        if len(new_token) < 50:
                            logging.error(
                                "Token reçu invalide (trop court): %s...",
                                new_token[:8],
                            )
                            continue

                        # Mise à jour en DB
                        token_metadata.previous_token = token_metadata.access_token
                        token_metadata.access_token = new_token
                        token_metadata.expires_at = now + timedelta(seconds=expires_in)
                        token_metadata.last_refresh_date = now
                        token_metadata.updated_at = now

                        session.commit()

                        logging.info(
                            "✓ Token Threads renouvelé avec succès pour %s (expire le %s)",
                            newspaper,
                            token_metadata.expires_at.strftime("%Y-%m-%d"),
                        )
                        return True

                    except requests.exceptions.HTTPError as http_err:
                        logging.error(
                            "Erreur HTTP lors du renouvellement (tentative %d/%d): %s",
                            attempt + 1,
                            max_retries,
                            http_err,
                        )
                        if attempt < max_retries - 1:
                            time.sleep(2**attempt)  # Backoff exponentiel
                    except Exception as err:
                        logging.error(
                            "Erreur lors du renouvellement (tentative %d/%d): %s",
                            attempt + 1,
                            max_retries,
                            err,
                        )
                        if attempt < max_retries - 1:
                            time.sleep(2**attempt)

                # Toutes les tentatives ont échoué
                logging.error(
                    "✗ ÉCHEC du renouvellement du token Threads pour %s après %d tentatives",
                    newspaper,
                    max_retries,
                )
                logging.error(
                    "⚠ ALERTE: Utilisation de l'ancien token - intervention manuelle recommandée"
                )
                return False  # On continue avec l'ancien token

            else:
                logging.debug(
                    "Token Threads %s valide encore %d jours",
                    newspaper,
                    days_until_expiration,
                )
                return True

    except SQLAlchemyError as err:
        logging.error("Erreur DB lors de la vérification du token Threads: %s", err)
        return True  # Continuer en cas d'erreur DB
    except Exception as err:
        logging.error("Erreur inattendue lors de la vérification du token: %s", err)
        return True


def get_token_dates(access_token):
    endpoint_url = "https://graph.threads.net/v1.0/debug_token"
    params = {"input_token": access_token, "access_token": access_token}
    try:
        response = requests.get(endpoint_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        token_data = data.get("data", {})
        expires_at_ts = token_data.get("expires_at")
        issued_at_ts = token_data.get("issued_at")
        if expires_at_ts and issued_at_ts:
            expires_at = datetime.fromtimestamp(expires_at_ts)
            issued_at = datetime.fromtimestamp(issued_at_ts)
            return expires_at, issued_at
        else:
            logging.error("Dates manquantes dans la réponse API")
            raise ValueError("Invalid API response")
    except requests.exceptions.HTTPError as http_err:
        logging.error("Erreur HTTP lors de la lecture des dates token: %s", http_err)
    except ValueError as json_err:
        logging.error("Réponse non-JSON ou invalide de l'API Threads: %s", json_err)
    except Exception as err:
        logging.error("Erreur inattendue lors de la récupération des dates: %s", err)

    # Fallback en cas d'erreur
    logging.warning("Utilisation dates par défaut suite à erreur API")
    now = datetime.now()
    return now + timedelta(days=60), now


def migrate_tokens_to_db(engine: Engine) -> None:
    """
    Migration one-time : transfère les tokens Threads du .env vers la base de données.

    Cette fonction doit être appelée une seule fois lors du premier déploiement
    de la nouvelle architecture. Elle crée les entrées TokensMetadata en DB.

    Args:
        engine: Moteur SQLAlchemy
    """
    newspapers = ["qdm", "qph"]

    try:
        with get_session(engine) as session:
            migrated = 0
            skipped = 0

            for newspaper in newspapers:
                # Vérifier si un token existe déjà en DB
                existing = session.execute(
                    select(TokensMetadata)
                    .where(TokensMetadata.network == "threads")
                    .where(TokensMetadata.newspaper == newspaper)
                ).scalar_one_or_none()

                if existing:
                    logging.info("Token Threads déjà migré pour %s - ignoré", newspaper)
                    skipped += 1
                    continue

                # Récupérer le token depuis .env
                token = os.getenv(f"THREADS_TOKEN_{newspaper.upper()}")

                if not token:
                    logging.warning(
                        "Aucun token Threads trouvé dans .env pour %s", newspaper
                    )
                    continue
                logging.debug("Token trouvé dans .env : %s", token)

                # Créer l'entrée en DB
                expires_at, issued_at = get_token_dates(token)
                if expires_at is None or issued_at is None:
                    logging.info("Pas de dates de token pour %s", newspaper)
                    continue

                new_token_metadata = TokensMetadata(
                    network="threads",
                    newspaper=newspaper,
                    access_token=token,
                    expires_at=expires_at,
                    created_at=issued_at,
                    is_active=True,
                )

                session.add(new_token_metadata)
                logging.info(
                    "Token Threads migré pour %s (expire: %s)",
                    newspaper,
                    new_token_metadata.expires_at.strftime("%Y-%m-%d"),
                )
                migrated += 1

            session.commit()
            logging.info(
                "Migration terminée - %d token(s) migré(s), %d ignoré(s)",
                migrated,
                skipped,
            )

    except SQLAlchemyError as err:
        logging.error("Erreur DB lors de la migration des tokens: %s", err)
    except Exception as err:
        logging.error("Erreur inattendue lors de la migration: %s", err)


def upload_img_to_bucket(post_image):
    remote_path = f"{os.getenv('BUCKET_PATH')}{post_image}"
    image_file = f"{image_path}/{post_image}"

    if not os.path.isfile(image_file):
        logging.error("Fichier introuvable pour upload: %s", image_file)
        raise FileNotFoundError(f"Local image not found: {image_file}")

    # Connexion SSH/SFTP
    hostname = os.getenv("HOSTNAME_FTP_BUCKET")
    port = int(os.getenv("PORT_BUCKET"))
    username = os.getenv("LOGIN_HOST_BUCKET")
    password = os.getenv("PWD_HOST_BUCKET")
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())

    sftp_session = None
    try:
        ssh.connect(hostname, port, username, password, timeout=10)
        logging.debug("Connexion SSH réussie")
        sftp_session = ssh.open_sftp()
        sftp_session.put(image_file, remote_path)
        logging.debug("Upload SFTP OK: %s -> %s", image_file, remote_path)
    except Exception as err:
        logging.error("Erreur SSH/SFTP %s", err)
        raise
    finally:
        try:
            if sftp_session:
                sftp_session.close()
        finally:
            ssh.close()


def delete_img_from_bucket(post_image):
    remote_path = f"{os.getenv('BUCKET_PATH')}{post_image}"

    # Connexion SSH/SFTP
    hostname = os.getenv("HOSTNAME_FTP_BUCKET")
    port = int(os.getenv("PORT_BUCKET"))
    username = os.getenv("LOGIN_HOST_BUCKET")
    password = os.getenv("PWD_HOST_BUCKET")

    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())

    sftp_session = None
    try:
        ssh.connect(hostname, port, username, password, timeout=10)
        logging.debug("Connexion SSH réussie")
        sftp_session = ssh.open_sftp()
        sftp_session.remove(remote_path)
        logging.debug("Suppression SFTP OK: %s", remote_path)
    except Exception as err:
        logging.error("Echec suppression SSH/SFTP %s", err)
    finally:
        try:
            if sftp_session:
                sftp_session.close()
        finally:
            ssh.close()


def post_to_threads(
    post, url_endpoint_media, url_endpoint_publish, tag, threads_token, http_session
):
    post_image = post["image_url"]
    uploaded_to_bucket = False
    if post_image and not re.search("^https?://", post_image):
        # Image en local, upload sur bucket
        upload_img_to_bucket(post_image)
        post_image = f"{os.getenv('BUCKET_URL')}{post_image}"
        uploaded_to_bucket = True

    # Create media container
    if post["link"] != "":
        payload = {
            "media_type": "IMAGE",
            "image_url": post_image,
            "text": f"{post['title']}\n\n➡️ {post['link']}{tag or ''}",
            "access_token": threads_token,
        }
    else:
        payload = {
            "media_type": "IMAGE",
            "image_url": post_image,
            "text": f"{post['title']}",
            "access_token": threads_token,
        }

    try:
        response = http_session.post(url_endpoint_media, data=payload)
        response.raise_for_status()
        creation_id = response.json().get("id")
        logging.debug("Connexion réussie à Threads")
        logging.debug("Creation_id : %s", creation_id)
    except requests.exceptions.HTTPError as http_err:
        logging.error("Erreur HTTP lors de la connexion à Threads : %s", http_err)
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error("Erreur de requête lors de la connexion à Threads : %s", req_err)
        return None
    except Exception as err:
        logging.error("Erreur inattendue lors de la connexion à Threads : %s", err)
        return None

    time.sleep(2)

    if creation_id is not None:
        try:
            payload = {
                "creation_id": creation_id,
                "access_token": threads_token,
            }
            response = http_session.post(url_endpoint_publish, data=payload, timeout=10)
            response.raise_for_status()
            threads_id = response.json().get("id")

            # Suppression de l'image uploadée sur le bucket
            if threads_id and uploaded_to_bucket:
                try:
                    pass
                    delete_img_from_bucket(post["image_url"])
                except Exception as err:
                    logging.error(
                        "Échec lors de la suppression sur le bucket : %s", err
                    )

            return threads_id
        except requests.exceptions.HTTPError as http_err:
            logging.error(
                "Erreur HTTP lors de la publication sur Threads : %s", http_err
            )
            return None
        except requests.exceptions.RequestException as req_err:
            logging.error(
                "Erreur de requête lors de la publication sur Threads : %s", req_err
            )
            return None
        except Exception as err:
            logging.error(
                "Erreur inattendue lors de la publication sur Threads : %s", err
            )
            return None


def get_threads_permalink(threads_id, threads_token, http_session):
    try:
        url_endpoint = f"https://graph.threads.net/v1.0/{threads_id}"
        params = {
            "fields": "permalink",
            "access_token": threads_token,
        }
        response = http_session.get(url_endpoint, params=params, timeout=10)
        response.raise_for_status()
        threads_permalink = response.json().get("permalink")
        return threads_permalink
    except requests.exceptions.HTTPError as http_err:
        logging.error(
            "Erreur HTTP lors de la récupération du lien Thread : %s", http_err
        )
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(
            "Erreur de requête lors de la récupération du lien Threads : %s", req_err
        )
        return None
    except Exception as err:
        logging.error(
            "Erreur inattendue lors de la récupération du lien Threads : %s", err
        )
        return None


def post_all_threads(posts, engine, newspaper, http_session):
    logging.debug("Début publication sur Threads")

    # Récupérer le token depuis la DB (avec fallback vers .env)
    threads_token = get_threads_token(engine, newspaper)
    if not threads_token:
        logging.error("THREADS_TOKEN manquant pour %s", newspaper)
        return

    tag = get_network_tag(engine, "Threads")
    url_endpoint_base = "https://graph.threads.net/v1.0/me/"
    url_endpoint_media = f"{url_endpoint_base}threads"
    url_endpoint_publish = f"{url_endpoint_base}threads_publish"

    for post in posts:
        threads_id = post_to_threads(
            post,
            url_endpoint_media,
            url_endpoint_publish,
            tag,
            threads_token,
            http_session,
        )
        if threads_id is not None:
            logging.debug("Publication Thread réussie id : %s", threads_id)
            network_post_link = get_threads_permalink(
                threads_id, threads_token, http_session
            )
            if network_post_link is not None:
                update_network_post_id(engine, post["post_id"], network_post_link)
            else:
                logging.error(
                    "Impossible de récupérer le permalink du Threads post id  %s",
                    post["post_id"],
                )
            modify_status(engine, post["post_id"], post["title"])


def post_all_facebook(posts, engine, newspaper, http_session):
    logging.info("[FACEBOOK] Début de publication des posts sur %s", newspaper)

    fb_token = os.getenv(f"FACEBOOK_TOKEN_{newspaper.upper()}")
    fb_page_id = os.getenv(f"FACEBOOK_PAGE_ID_{newspaper.upper()}")

    if not fb_token or not fb_page_id:
        logging.warning("[Facebook] Credentials manquants pour %s", newspaper)
        return

    tag = get_network_tag(engine, "Facebook")
    BASE_URL = f"https://graph.facebook.com/v25.0/{fb_page_id}"

    for post in posts:
        raw_link = post.get("link") or ""
        link = raw_link + (tag or "") if raw_link else ""
        message = f"{post['tagline']}"

        post_image = post["image_url"]

        payload = {
            "message": message,
            "published": "true",
            "access_token": fb_token,
        }
        try:
            if post_image and not re.search("^https?://", post_image):
                url = f"{BASE_URL}/photos"
                with open(f"{image_path}/{post_image}", "rb") as f:
                    files = {"source": f}
                    response = http_session.post(url, data=payload, files=files)
            else:
                payload["link"] = link
                url = f"{BASE_URL}/feed"
                response = http_session.post(url, data=payload)

            response.raise_for_status()
            fb_post_id = response.json().get("id", "")
            post_id_part = (
                fb_post_id.split("_")[-1] if "_" in fb_post_id else fb_post_id
            )
            post_url = f"https://www.facebook.com/{fb_page_id}/posts/{post_id_part}"
            update_network_post_id(engine, post["post_id"], post_url)
            modify_status(engine, post["post_id"], post["title"])
            logging.info("[Facebook] Post publié : %s", post_url)

        except Exception as e:
            logging.error(
                "[Facebook] Erreur publication post %s : %s", post["post_id"], e
            )


# ================================================
# Publication des posts sur le journal sélectionné
# ================================================


def post_auto_function(
    engine: Engine, newspaper: str, http_session: requests.Session
) -> None:
    """
    Traite et publie les posts planifiés pour un journal sur différents réseaux sociaux.

    Args:
        engine: Moteur SQLAlchemy pour l'accès à la base de données
        newspaper: Nom du journal (qdm, qph)
        http_session: Session HTTP réutilisable pour les requêtes
    """
    NETWORK_FUNCTIONS = {
        "X": post_all_x,
        "Bluesky": post_all_bluesky,
        "Threads": post_all_threads,
        "Facebook": post_all_facebook,
    }

    logging.info("Traitement de posts %s", newspaper)

    for network, handler in NETWORK_FUNCTIONS.items():
        posts = fetch_posts(engine, network, newspaper)

        if posts:
            handler(posts, engine, newspaper, http_session)
        else:
            logging.info("Aucun post %s sur %s", network, newspaper)

    logging.info("Fin traitement de posts %s", newspaper)


# ============================================
# MAIN
# ============================================


def main() -> None:
    global image_path

    if os.getenv("DOCKER_ENV"):
        database_path = str(script_dir / os.getenv("DATABASE_PATH"))
        log_path = str(script_dir / os.getenv("LOG_PATH"))
        image_path = str(script_dir / os.getenv("IMAGES_PATH"))
    else:
        database_path = str(script_dir.parent.parent / os.getenv("DATABASE_PATH"))
        log_path = str(script_dir.parent.parent / os.getenv("LOG_PATH"))
        image_path = str(
            script_dir.parent.parent / "medpost-app" / os.getenv("IMAGES_PATH")
        )

    logging.basicConfig(
        filename=log_path,
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M",
    )

    url_newspapers = {
        "qdm": os.getenv("QDM_URL_RSS"),
        "qph": os.getenv("QPH_URL_RSS"),
    }

    engine = create_db_and_tables(database_path)

    # Utilisation de la session HTTP optimisée
    with create_http_session() as http_session:
        # Migration des tokens du .env vers la DB (one-time, idempotent)
        logging.info("=== Vérification des tokens Threads ===")
        migrate_tokens_to_db(engine)

        logging.info("=== Début du traitement de publication ===")
        for newspaper, url_newspaper in url_newspapers.items():
            logging.info("Traitement du journal: %s", newspaper)

            # Vérifier et renouveler le token si nécessaire
            check_and_refresh_threads_token(engine, newspaper)

            post_auto_function(engine, newspaper, http_session)

            logging.info("Fin traitement du journal: %s", newspaper)

        logging.info("=== Traitement de publication terminé ===")


if __name__ == "__main__":
    from datetime import datetime
    from datetime import timedelta
    from paramiko import SSHClient, AutoAddPolicy

    main()
