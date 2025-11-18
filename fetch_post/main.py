import logging
import os

# import re
# import io
import requests
import tweepy
import feedparser

# from PIL import Image
from datetime import datetime

# from xmlrpc.client import boolean
from requests_oauthlib import OAuth1
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError, NoResultFound, MultipleResultsFound
from database import Articles_rss, Posts, Networks, create_db_and_tables, get_session
from atproto import models, Client
from bs4 import BeautifulSoup as bs
# from dotenv import load_dotenv

###### Fonctions de post_auto


def fetch_posts(engine, selectedfeed, newspaper):
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


def connect_x_apiv2(x_api_key, x_api_secret, x_access_token, x_access_token_secret):
    return tweepy.Client(
        consumer_key=x_api_key,
        consumer_secret=x_api_secret,
        access_token=x_access_token,
        access_token_secret=x_access_token_secret,
    )


def update_network_post_id(engine, post_id, network_post_id):
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


def modify_status(engine, post_id, post_title):
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


def get_network_tag(engine, network):
    try:
        with get_session(engine) as session:
            tag = session.scalar(select(Networks.tag).where(Networks.name == network))
            return tag
    except Exception as err:
        logging.error("Impossible d'accéder au tag de %s : Erreur %s", network, err)
        return None


def post_to_x(api, post, tag, media_id):
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
    x_api_key, x_api_secret, x_access_token, x_access_token_secret, image_path
):
    image_path = "static/" + image_path
    auth = OAuth1(x_api_key, x_api_secret, x_access_token, x_access_token_secret)
    upload_url = "https://upload.twitter.com/1.1/media/upload.json"
    with open(image_path, "rb") as image_file:
        files = {"media": image_file}
        try:
            req = requests.post(url=upload_url, auth=auth, files=files)
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


def post_all_x(posts, engine, newspaper):
    #    load_dotenv()
    #    image_path = os.getenv('IMAGES_PATH')
    x_api_secret = os.getenv("API_KEY_SECRET_" + newspaper.upper())
    x_api_key = os.getenv("API_KEY_" + newspaper.upper())
    x_access_token = os.getenv("ACCESS_TOKEN_" + newspaper.upper())
    x_access_token_secret = os.getenv("ACCESS_TOKEN_SECRET_" + newspaper.upper())
    x_url = os.getenv("X_URL_" + newspaper.upper())
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
        if post["article_image_url"] != "images/no_picture.jpg":
            media_id = []  # Pas besoin d'uploader une image
            success, network_post_id = post_to_x(x_apiv2, post, tag, media_id)
        # Article sans image, post avec image uploadée
        elif post["image_url"] != "":
            retour_id = upload_image_to_x(
                x_api_key,
                x_api_secret,
                x_access_token,
                x_access_token_secret,
                post["image_url"],
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


def post_to_bluesky(post, client_bluesky, tag):
    image_url = post["image_url"]
    if post["article_image_url"] != "images/no_picture.jpg":
        try:
            response = requests.get(image_url, timeout=10)
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
            logging.info("Upload de l'image Bluesky OK %s", post["title"])
        except requests.exceptions.HTTPError as err:
            logging.error("Erreur HTTP lors de la lecture de image_url : %s", err)
            return None
    else:  # Récupérer l'image en local
        image_path = "static/" + image_url
        try:
            with open(image_path, "rb") as image_file:
                img_data = image_file.read()
        except Exception as e:
            logging.error("Erreur lors du load de l'image %s : %s", image_url, e)
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


def post_all_bluesky(posts, engine, newspaper):
    bluesky_login = os.getenv("BLUESKY_LOGIN_" + newspaper.upper())
    bluesky_password = os.getenv("BLUESKY_PASSWORD_" + newspaper.upper())
    bluesky_url = os.getenv("BLUESKY_URL_" + newspaper.upper())
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
        network_post_id = post_to_bluesky(post, client_bluesky, tag)
        if network_post_id is not None:
            network_post_link = bluesky_url + str(network_post_id)
            update_network_post_id(engine, post["post_id"], network_post_link)
            modify_status(engine, post["post_id"], post["tagline"])


###### Fonctions de fetch_rss
def fetch_rss(url: str) -> list[dict] | None:
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


def is_valid_article(item: str) -> bool:
    if item.title == "Votre journal au format numérique":
        return False
    else:
        return True


def normalize_spaces(text):
    return " ".join(text.split())


def convert_date(date_str):
    return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")


def fetch_article_html(url: str):
    try:
        logging.debug("Lecture des données articles url : %s", url)
        http_response = requests.get(url, timeout=10)
        html_article = bs(http_response.text, "html.parser")
        logging.debug("Fetch article url : %s", url)
        return html_article
    except requests.exceptions.RequestException as e:
        logging.error("Échec lors de la lecture URL %s : %s", url, e)


def get_article_nid(html_article):
    # <article data-history-node-id="248526"
    try:
        nid_article = html_article.article["data-history-node-id"]
        logging.debug("NID : %s", nid_article)
        return nid_article
    except Exception:
        logging.error("Pas de NID pour l'article")
        return None


def is_article_in_db(session, nid_article):
    stmt = select(Articles_rss).where(Articles_rss.nid == nid_article)
    article_in_db = session.execute(stmt).scalars().first()
    logging.debug("Article in db : %s", article_in_db)
    return article_in_db


def extract_article_data(html_article, nid_article, pubdate, newspaper):
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


def store_new_article(session, new_article) -> bool:
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


def update_article_in_db(session, new_article) -> bool:
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


def login_qdm(session):
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


def load_articles(engine, newspaper, url_rss):
    """
    Charge les articles depuis un flux RSS et les stocke en base de données.

    Args:
        engine: Moteur SQLAlchemy
        newspaper: Nom du journal (qdm, qph)
        url_rss: URL du flux RSS
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
    logging.info("Lecture des articles du flux %s", newspaper)

    for itemrss in feed:
        # Valdidation de l'article
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

        # Récupération du HTML de l'article
        try:
            html_article = fetch_article_html(itemrss.link)
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


def post_auto_function(engine, newspaper):
    networks = ["X", "Bluesky"]  # Active networks
    logging.info("Traitement de posts %s", newspaper)
    for network in networks:
        posts = fetch_posts(engine, network, newspaper)
        if posts != []:
            if network == "X":
                post_all_x(posts, engine, newspaper)
            elif network == "Bluesky":
                post_all_bluesky(posts, engine, newspaper)
        else:
            logging.info("Aucun post %s sur %s", network, newspaper)
    logging.info("Fin traitement de posts %s", newspaper)


###### MAIN
def main():
    # load_dotenv(dotenv_path='/Users/stephanelong/Documents/DEV/Medpost/fetch_post/.env')
    log_path = os.getenv("LOG_PATH")
    database_path = os.getenv("DATABASE_PATH")
    url_newspapers = {"qdm": os.getenv("QDM_URL_RSS"), "qph": os.getenv("QPH_URL_RSS")}
    #    url_newspapers = {'qdm': '/app/rss.xml', 'qph':os.getenv('QPH_URL_RSS')}
    logging.basicConfig(
        filename=log_path,
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M",
    )
    engine = create_db_and_tables(database_path)
    for newspaper, url_newspaper in url_newspapers.items():
        load_articles(engine, newspaper, url_newspaper)
        post_auto_function(engine, newspaper)


if __name__ == "__main__":
    main()
