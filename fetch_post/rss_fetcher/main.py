"""Service RSS Fetcher - Lecture et stockage des articles depuis les flux RSS"""

import logging
import os
import platform
import time
from typing import Any, Optional
from pathlib import Path

import requests
import feedparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError, NoResultFound, MultipleResultsFound
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup as bs
import re

# Import des modèles de la base de données
from database import (
    Articles_rss,
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
# FONCTIONS DE COLLECTE DES ARTICLES (FETCH_RSS)
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


def convert_date(date_str: str) -> Any:
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
        image_path = str(script_dir.parent.parent / "medpost-app" / os.getenv("IMAGES_PATH"))

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
        logging.info("=== Début du traitement RSS ===")
        for newspaper, url_newspaper in url_newspapers.items():
            logging.info("Traitement du journal: %s", newspaper)
            load_articles(engine, newspaper, url_newspaper, http_session)
            logging.info("Fin traitement du journal: %s", newspaper)

        logging.info("=== Traitement RSS terminé ===")


if __name__ == "__main__":
    from datetime import datetime
    main()
