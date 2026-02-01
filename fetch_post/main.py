"""MedpostBot Version 1.0"""

import logging
import os
import platform
import time
from typing import Any, Optional
from collections.abc import Sequence

import re

import requests
import tweepy
import feedparser

from datetime import datetime

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests_oauthlib import OAuth1
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError, NoResultFound, MultipleResultsFound
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from database import Articles_rss, Posts, Networks, TokensMetadata, create_db_and_tables, get_session
from atproto import models, Client
from bs4 import BeautifulSoup as bs

# from dotenv import load_dotenv
from pathlib import Path
from paramiko import SSHClient, AutoAddPolicy

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
    # bot_url = os.getenv("BOT_URL", "https://github.com/stephane-long/medpost")
    bot_contact = os.getenv("BOT_CONTACT", "agenthttp.recognize312@passmail.net")

    # Construction du User-Agent
    # Format: NomBot/Version (+URL; email) Client/Version Système
    user_agent = (
        f"{bot_name}/{bot_version} "
        # f"(+{bot_url}; {bot_contact}) "
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
    #    image_file = f"{str(script_dir.parent)}{os.getenv('IMAGES_PATH')}{image_file}"
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
    #    load_dotenv()
    #    image_file = os.getenv('IMAGES_PATH')
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
        #        image_file = f"{str(script_dir.parent)}{os.getenv('IMAGES_PATH')}{post_image}"
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
            # img_data_clean = clean_and_resize_image(img_data, max_size=900000)
            # if img_data_clean is None:
            #    logging.error("Impossible de réduire l'image sous 1 Mo pour %s", post['title'])
            #    return
            #            response = client_bluesky.send_image(text=post['tagline'], image=img_data_clean, image_alt='')
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
                .where(TokensMetadata.is_active == True)
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


def check_and_refresh_threads_token(
    engine: Engine, newspaper: str, http_session: requests.Session
) -> bool:
    """
    Vérifie l'expiration du token Threads et le renouvelle si nécessaire.

    Args:
        engine: Moteur SQLAlchemy
        newspaper: Nom du journal (qdm/qph)
        http_session: Session HTTP pour les requêtes

    Returns:
        bool: True si le token est valide (ou renouvelé avec succès), False sinon
    """
    try:
        with get_session(engine) as session:
            token_metadata = session.execute(
                select(TokensMetadata)
                .where(TokensMetadata.network == "threads")
                .where(TokensMetadata.newspaper == newspaper)
                .where(TokensMetadata.is_active == True)
            ).scalar_one_or_none()

            if not token_metadata:
                logging.warning(
                    "Aucun token Threads en DB pour %s - vérification ignorée", newspaper
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

                        response = http_session.get(
                            refresh_url, params=params, timeout=10
                        )
                        response.raise_for_status()

                        data = response.json()
                        new_token = data.get("access_token")
                        expires_in = data.get("expires_in", 5184000)  # 60 jours par défaut

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
                        token_metadata.expires_at = now + timedelta(
                            seconds=expires_in
                        )
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
        logging.error(
            "Erreur DB lors de la vérification du token Threads: %s", err
        )
        return True  # Continuer en cas d'erreur DB
    except Exception as err:
        logging.error("Erreur inattendue lors de la vérification du token: %s", err)
        return True


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
                    logging.info(
                        "Token Threads déjà migré pour %s - ignoré", newspaper
                    )
                    skipped += 1
                    continue

                # Récupérer le token depuis .env
                token = os.getenv(f"THREADS_TOKEN_{newspaper.upper()}")

                if not token:
                    logging.warning(
                        "Aucun token Threads trouvé dans .env pour %s", newspaper
                    )
                    continue

                # Créer l'entrée en DB
                now = datetime.now()
                new_token_metadata = TokensMetadata(
                    network="threads",
                    newspaper=newspaper,
                    access_token=token,
                    expires_at=now + timedelta(days=60),  # 60 jours par défaut
                    created_at=now,
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
    #    image_file = f"{str(script_dir.parent)}{os.getenv('IMAGES_PATH')}{post_image}"
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

    # Vérifier et renouveler le token si nécessaire
    check_and_refresh_threads_token(engine, newspaper, http_session)

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


# ============================================
# FONCTIONS DE COLLECTE DES ARTICES (FETCH_RSS)
# ============================================


def fetch_rss(url: str) -> Optional[list[dict[str, Any]]]:
    """
    Récupère les entrées du flux RSS QDM/QPH à partir d'une URL donnée.

    Args:
        url (str): L'URL du flux RSS.

    Returns:
        list[dict] | None: Une liste de dictionnaires contenant les entrées du flux RSS,
                           ou None en cas d'erreur.
    """
    logging.info("Début d'import RSS %s", url)
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            raise ValueError(feed.bozo_exception)
        logging.info("Lecture du flux RSS réussie %s", url)

        # DEBUG: Analyser le premier item
        if len(feed.entries) > 0:
            first = feed.entries[0]
            logging.debug("=== PREMIER ITEM ===")
            logging.debug("Titre: %s", first.get("title", "NO TITLE"))
            logging.debug("Link (direct): %s", first.get("link", "NO LINK"))
            logging.debug("Attribut link: %s", getattr(first, "link", "NO ATTR"))
            logging.debug("Toutes les clés: %s", list(first.keys()))

        return feed.entries

    except Exception as e:
        logging.error("Lecture du flux RSS impossible : %s", e)
        return None


def is_valid_article(item: Any) -> bool:
    if item.title == "Votre journal au format numérique":
        return False
    else:
        return True


def normalize_spaces(text: str) -> str:
    return " ".join(text.split())


def convert_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")


def fetch_article_html(
    url: str, session: requests.Session, max_retries: int = 3
) -> Optional[bs]:
    """
    Récupère le HTML d'un article avec gestion robuste des erreurs.

    Args:
        url: URL de l'article
        session: Session HTTP configurée avec create_http_session()
        max_retries: Nombre max de tentatives manuelles

    Returns:
        BeautifulSoup | None: HTML parsé ou None si échec
    """
    for attempt in range(max_retries):
        try:
            logging.debug(
                "Lecture article %s (tentative %d/%d)", url, attempt + 1, max_retries
            )

            # Le retry automatique de la session gère déjà les erreurs 5xx
            http_response = session.get(url, timeout=10)

            # Gestion spécifique du rate limiting (429)
            if http_response.status_code == 429:
                retry_after = int(http_response.headers.get("Retry-After", 60))
                logging.warning(
                    "Rate limit atteint, attente de %s secondes", retry_after
                )
                time.sleep(retry_after)
                continue

            # Lever une exception pour les autres codes d'erreur
            http_response.raise_for_status()

            # Succès: parser le HTML
            html_article = bs(http_response.text, "html.parser")
            logging.debug("Article récupéré avec succès: %s", url)
            return html_article

        except requests.exceptions.Timeout:
            logging.warning(
                "Timeout lors de la lecture de %s (tentative %d/%d)",
                url,
                attempt + 1,
                max_retries,
            )
            if attempt == max_retries - 1:
                logging.error("Échec définitif (timeout) pour %s", url)
                return None
            time.sleep(2**attempt)  # Backoff: 1s, 2s, 4s

        except requests.exceptions.HTTPError as e:
            logging.error("Erreur HTTP %s pour %s", e.response.status_code, url)
            return None

        except requests.exceptions.RequestException as e:
            logging.error("Erreur réseau pour %s: %s", url, e)
            if attempt == max_retries - 1:
                return None
            time.sleep(2**attempt)

    return None


def get_article_nid(html_article: bs) -> Optional[str]:
    # <article data-history-node-id="248526"
    try:
        nid_article = html_article.article["data-history-node-id"]
        logging.debug("NID : %s", nid_article)
        return nid_article
    except Exception:
        logging.error("Pas de NID pour l'article")
        return None


def is_article_in_db(session: Session, nid_article: str) -> Optional[Articles_rss]:
    stmt = select(Articles_rss).where(Articles_rss.nid == nid_article)
    article_in_db = session.execute(stmt).scalars().first()
    logging.debug("Article in db : %s", article_in_db)
    return article_in_db


def extract_article_data(
    html_article: bs, nid_article: str, pubdate: str, newspaper: str
) -> Optional[dict[str, Any]]:
    """
    Extrait les données d'un article HTML avec gestion des erreurs.

    Args:
        html_article: Objet BeautifulSoup de l'article
        nid_article: ID de l'article
        pubdate: Date de publication (string)
        newspaper: Nom du journal

    Returns:
        dict: Dictionnaire contenant les données de l'article, ou None si extraction impossible
    """
    # Validation des paramètres d'entrée
    if html_article is None:
        logging.error("html_article est None pour NID %s", nid_article)
        return None

    if not nid_article:
        logging.error("nid_article manquant ou vide")
        return None

    new_article = {}
    new_article["nid"] = nid_article
    new_article["newspaper"] = newspaper

    # Extraction du titre
    try:
        title_meta = html_article.find("meta", attrs={"name": "twitter:title"})
        if title_meta and title_meta.get("content"):
            new_article["title"] = title_meta["content"]
        else:
            new_article["title"] = "Sans titre"
            logging.warning("Titre twitter:title manquant pour NID %s", nid_article)
    except (AttributeError, KeyError) as e:
        logging.error("Erreur extraction titre pour NID %s: %s", nid_article, e)
        new_article["title"] = "Sans titre"

    # Extraction du lien
    try:
        url_meta = html_article.find("meta", attrs={"name": "twitter:url"})
        if url_meta and url_meta.get("content"):
            new_article["link"] = url_meta["content"]
        else:
            new_article["link"] = ""
            logging.warning("URL twitter:url manquante pour NID %s", nid_article)
    except (AttributeError, KeyError) as e:
        logging.error("Erreur extraction URL pour NID %s: %s", nid_article, e)
        new_article["link"] = ""

    # Extraction du résumé
    try:
        desc_meta = html_article.find("meta", attrs={"name": "twitter:description"})
        if desc_meta and desc_meta.get("content"):
            new_article["summary"] = desc_meta["content"]
        else:
            new_article["summary"] = ""
            logging.warning(
                "Description twitter:description manquante pour NID %s", nid_article
            )
    except (AttributeError, KeyError) as e:
        logging.error("Erreur extraction résumé pour NID %s: %s", nid_article, e)
        new_article["summary"] = ""

    # Extraction de l'image
    new_article["image_url"] = "images/no_picture.jpg"  # Valeur par défaut
    try:
        image_meta = html_article.find("meta", attrs={"name": "twitter:image"})
        if image_meta and image_meta.get("content"):
            new_article["image_url"] = image_meta["content"]
    except (AttributeError, KeyError) as e:
        logging.warning(
            "Erreur extraction image pour NID %s: %s, utilisation image par défaut",
            nid_article,
            e,
        )

    # Conversion de la date avec gestion d'erreur
    try:
        new_article["pubdate"] = convert_date(pubdate)
    except (ValueError, TypeError) as e:
        logging.error(
            "Erreur conversion date '%s' pour NID %s: %s, utilisation date actuelle",
            pubdate,
            nid_article,
            e,
        )
        new_article["pubdate"] = datetime.now()

    new_article["online"] = 1

    return new_article


def store_new_article(session: Session, new_article: dict[str, Any]) -> bool:
    new_article_db = Articles_rss(
        title=normalize_spaces(new_article["title"]),
        nid=new_article["nid"],
        link=new_article["link"],
        summary=new_article["summary"],
        image_url=new_article["image_url"],
        pubdate=new_article["pubdate"],
        online=new_article["online"],
        newspaper=new_article["newspaper"],
    )
    try:
        session.add(new_article_db)
        session.commit()
        logging.debug(
            "Article enregistré avec succès : NID %s - %s",
            new_article["nid"],
            new_article["title"],
        )
        return True
    except SQLAlchemyError as err:
        session.rollback()
        logging.error(
            "Impossible d'enregistrer l'article NID %s: %s",
            new_article.get("nid", "UNKNOWN"),
            err,
        )
        return False
    except Exception as err:
        session.rollback()
        logging.error(
            "Erreur inattendue lors de l'enregistrement de l'article: %s", err
        )
        return False


def update_article_in_db(session: Session, new_article: dict[str, Any]) -> bool:
    if not new_article or "nid" not in new_article:
        logging.error("Données d'article invalides pour la mise à jour")
        return False

    stmt = select(Articles_rss).where(Articles_rss.nid == new_article["nid"])

    try:
        article = session.scalars(stmt).one()
        logging.debug(
            "Article trouvé pour mise à jour : %s (NID: %s)",
            article.title,
            new_article["nid"],
        )
        article.title = normalize_spaces(new_article.get("title", article.title))
        article.link = new_article.get("link", article.link)
        article.summary = new_article.get("summary", article.summary)
        article.image_url = new_article.get("image_url", article.image_url)
        article.pubdate = new_article.get("pubdate", article.pubdate)
        article.online = new_article.get("online", article.online)
        session.commit()
        logging.debug("Article mis à jour : %s", article.title)
        return True

    except NoResultFound:
        logging.error(
            "Article non trouvé pour mise à jour (NID: %s)",
            new_article.get("nid", "UNKNOWN"),
        )
        return False

    except MultipleResultsFound:
        logging.warning(
            "PROBLEME DB : Plusieurs articles avec le même NID %s détectés !",
            new_article.get("nid", "UNKNOWN"),
        )
        session.rollback()
        return False

    except SQLAlchemyError as err:
        session.rollback()
        logging.error(
            "Erreur SQLAlchemy lors de la mise à jour de l'article (NID: %s): %s",
            new_article.get("nid", "UNKNOWN"),
            err,
        )
        return False

    except Exception as err:
        session.rollback()
        logging.error(
            "Erreur inattendue lors de la mise à jour de l'article (NID: %s): %s",
            new_article.get("nid", "UNKNOWN"),
            err,
        )
        return False


def login_qdm(session: requests.Session) -> bool:
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    login_url = os.getenv("LOGIN_URL")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": login_url,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    payload = {
        "name": username,
        "pass": password,
        "form_build_id": "form-P-mW6y9GQx_muaK48sJ7fg1LxJi1TIjfr6utScmKBzs",
        "form_id": "user_login_form",
        "destination": "/homepage",
        "op": "Se connecter",
    }
    try:
        logging.info(f"Tentative de connexion pour l'utilisateur {username}...")
        response = session.post(
            login_url, data=payload, headers=headers, allow_redirects=False
        )
        if response.status_code == 303:
            logging.info(
                "Connexion réussie (redirection 303 reçue). La session est authentifiée."
            )
            return True
        else:
            logging.error(
                "Échec de la connexion. Le serveur n'a pas renvoyé de redirection (code 303)."
            )
            logging.error(f"Statut reçu : {response.status_code}")
            return False

    except requests.RequestException as e:
        logging.error(
            f"Une erreur de connexion est survenue lors de la tentative de login : {e}"
        )
        return False


def load_articles(
    engine: Engine, newspaper: str, url_rss: str, http_session: requests.Session
) -> None:
    """
    Charge les articles depuis un flux RSS et les stocke en base de données.

    Args:
        engine: Moteur SQLAlchemy
        newspaper: Nom du journal (qdm, qph)
        url_rss: URL du flux RSS
        http_session: Session HTTP réutilisable
    """
    #    URL_RSS = os.getenv('QDM_URL_RSS')
    feed = fetch_rss(url_rss)
    if not feed:
        logging.warning("Flux RSS vide ou inaccessible pour %s", newspaper)
        return

    nb_itemrss = 0
    new_articles = 0
    updated_articles = 0
    max_articles = 25
    errors = 0

    # Délai respectueux entre requêtes
    crawl_delay = float(os.getenv("CRAWL_DELAY", "1.5"))

    logging.info("Lecture des articles du flux %s", newspaper)

    for itemrss in feed:
        # Validation de l'article
        if not is_valid_article(itemrss):
            logging.debug(
                "Article invalide ignoré: %s", getattr(itemrss, "title", "N/A")
            )
            continue

        # Vérification de la présence du lien
        if not hasattr(itemrss, "link") or not itemrss.link:
            logging.error("Article sans lien: %s", getattr(itemrss, "title", "N/A"))
            errors += 1
            continue

        # Délai respectueux avant chaque requête
        if nb_itemrss > 0:  # Pas de délai pour le premier article
            time.sleep(crawl_delay)

        # Récupération du HTML de l'article avec session partagée
        try:
            html_article = fetch_article_html(itemrss.link, http_session)
            if html_article is None:
                logging.error("Impossible de récupérer le HTML pour: %s", itemrss.link)
                errors += 1
                continue
        except Exception as err:
            logging.error("Erreur lors du fetch HTML de %s: %s", itemrss.link, err)
            errors += 1
            continue

        # Extraction du NID
        nid_article = get_article_nid(html_article)
        if nid_article is None:
            logging.error("NID absent pour l'article: %s", itemrss.link)
            errors += 1
            continue

        # Extraction des données
        try:
            new_article = extract_article_data(
                html_article, nid_article, itemrss.published, newspaper
            )
            # Validation des données extraites
            if new_article is None:
                logging.error("Extraction impossible pour article NID %s", nid_article)
                errors += 1
                continue

        except Exception as err:
            logging.error(
                "Erreur extraction données de l'article (NID %s: %s", nid_article, err
            )
            errors += 1
            continue

        # Stockage en base avec session dédiée
        try:
            with get_session(engine) as session:
                existing_article = is_article_in_db(session, nid_article)

                if existing_article is None:
                    # Nouvel article
                    if store_new_article(session, new_article):
                        logging.debug(
                            "Article stocké: %s (NID: %s)",
                            new_article["title"],
                            nid_article,
                        )
                        new_articles += 1
                    else:
                        logging.error(
                            "Échec stockage: %s (NID: %s)",
                            new_article["title"],
                            nid_article,
                        )
                        errors += 1
                else:
                    # Mise à jour
                    if update_article_in_db(session, new_article):
                        logging.debug(
                            "Article mis à jour: %s (NID: %s)",
                            new_article["title"],
                            nid_article,
                        )
                        updated_articles += 1
                    else:
                        logging.error(
                            "Échec MAJ: %s (NID: %s)", new_article["title"], nid_article
                        )
                        errors += 1

        except SQLAlchemyError as err:
            logging.error("Erreur DB pour NID %s: %s", nid_article, err)
            errors += 1

        except Exception as err:
            logging.error("Erreur inattendue pour NID %s: %s", nid_article, err)
            errors += 1

        nb_itemrss += 1
        if nb_itemrss >= max_articles:
            break

    # Rapport final
    logging.info(
        "Fin lecture flux %s - %d lu(s), %d nouveau(x), %d MAJ, %d erreur(s)",
        newspaper,
        nb_itemrss,
        new_articles,
        updated_articles,
        errors,
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
    # load_dotenv(dotenv_path=str(script_dir / ".env.dev"))

    if os.getenv("DOCKER_ENV"):
        database_path = str(script_dir / os.getenv("DATABASE_PATH"))
        log_path = str(script_dir / os.getenv("LOG_PATH"))
        image_path = str(script_dir / os.getenv("IMAGES_PATH"))
    else:
        database_path = str(script_dir.parent / os.getenv("DATABASE_PATH"))
        log_path = str(script_dir.parent / os.getenv("LOG_PATH"))
        image_path = str(script_dir.parent / "medpost-app" / os.getenv("IMAGES_PATH"))

    logging.basicConfig(
        filename=log_path,
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M",
    )

    #    log_path = str(script_dir.parent / os.getenv("LOG_PATH"))
    #    database_path = str(script_dir.parent / os.getenv("DATABASE_PATH"))
    url_newspapers = {"qdm": os.getenv("QDM_URL_RSS"), "qph": os.getenv("QPH_URL_RSS")}

    engine = create_db_and_tables(database_path)

    # Migration des tokens du .env vers la DB (one-time, idempotent)
    migrate_tokens_to_db(engine)

    # Utilisation de la session HTTP optimisée
    with create_http_session() as http_session:
        logging.info("=== Début du traitement ===")

        for newspaper, url_newspaper in url_newspapers.items():
            logging.info("Traitement du journal: %s", newspaper)

            load_articles(engine, newspaper, url_newspaper, http_session)
            post_auto_function(engine, newspaper, http_session)

            logging.info("Fin traitement du journal: %s", newspaper)

        logging.info("=== Traitement terminé ===")


if __name__ == "__main__":
    main()
