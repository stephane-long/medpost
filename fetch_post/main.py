import logging
import os
# import re
import io
import requests
import tweepy
import feedparser
#from PIL import Image
from datetime import datetime
from xmlrpc.client import boolean
from requests_oauthlib import OAuth1
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from database import Articles_rss, Posts, Networks, create_db_and_tables, get_session
from atproto import models, Client
from bs4 import BeautifulSoup as bs
# from dotenv import load_dotenv

###### Fonctions de post_auto

def fetch_posts(engine, selectedfeed, newspaper):
    with get_session(engine) as session:
        statement = (select(Posts.title,
                            Posts.description,
                            Posts.tagline,
                            Posts.image_url,
                            Articles_rss.id.label('article_id'),
                            Articles_rss.link,
                            Articles_rss.image_url.label('article_image_url'),
                            Networks.name.label('network_name'),
                            Posts.id.label('post_id'))
                     .join(Articles_rss, Articles_rss.id == Posts.id_article)
                     .join(Networks, Networks.id == Posts.network)
                     .where(Networks.name == selectedfeed)
                     .where(Posts.status == 'plan')
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
    return tweepy.Client(consumer_key=x_api_key,
                         consumer_secret=x_api_secret,
                         access_token=x_access_token,
                         access_token_secret=x_access_token_secret)

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
            logging.debug("Transaction committée avec succès post ID: %s",
                           post_id)
        except SQLAlchemyError as e:
            session.rollback()
            logging.error("Erreur lors de la MAJ du network_post_id du post %s: %s",
                           post_id, e)
        except Exception as e:
            session.rollback()
            logging.error("Erreur inattendue lors de la MAJ du network_post_id pour le post %s: %s",
                           post_id, e)

def modify_status(engine, post_id, post_title):
    with get_session(engine) as session:
        try:
            statement = (update(Posts).
                         where(Posts.id == post_id)
                         .values(status='pub')
            )
            session.execute(statement)
            session.commit()
            logging.info("Mise à jour du statut de publication de %s", post_title)
        except Exception as e:
            logging.error("Erreur %s lors de modification du status post %s", e, post_title)

def get_network_tag(engine, network):
    try:
        with get_session(engine) as session:
            tag = session.scalar(select(Networks.tag).where(Networks.name == network))
            return tag
    except Exception as err:
        logging.error("Impossible d'accéder au tag de %s : Erreur %s", network, err)
        return None

def post_to_x(api, post, tag, media_id):
    if post['link'] != '':
        url_to_post = post['link'] + tag
    else:
        url_to_post = ''
    post_content = f"{post['title']} {url_to_post}"
    try:
        if media_id == []:
            response = api.create_tweet(text=post_content)
        else:
            response = api.create_tweet(text=post_content, media_ids=media_id)
        network_post_id = response.data['id']
        logging.info("Tweet publié - ID : %s Link : %s - media : %s", network_post_id, url_to_post, media_id)
        return True, network_post_id
    except Exception as e:
        logging.error("Échec du post: %s\n%s", e, post_content)
        return False, None

def upload_image_to_x(x_api_key, x_api_secret, x_access_token, x_access_token_secret, image_path):
    image_path = "static/" + image_path
    auth = OAuth1(x_api_key, x_api_secret, x_access_token, x_access_token_secret)
    upload_url = "https://api.x.com/2/media/upload"  
    with open(image_path, 'rb') as image_file:
        files = {'media': image_file}
        req = requests.post(
            url=upload_url,
            auth=auth,
            files=files)
    media_id = req.json()['id']
    return media_id

def post_all_x(posts, engine, newspaper):
#    load_dotenv()
#    image_path = os.getenv('IMAGES_PATH')
    x_api_secret = os.getenv('API_KEY_SECRET_'+newspaper.upper())
    x_api_key = os.getenv('API_KEY_'+newspaper.upper())
    x_access_token = os.getenv('ACCESS_TOKEN_'+newspaper.upper())
    x_access_token_secret = os.getenv('ACCESS_TOKEN_SECRET_'+newspaper.upper())
    x_url = os.getenv('X_URL_'+newspaper.upper())
    # Connexion à X API V2
    try:
        x_apiv2 = connect_x_apiv2(x_api_key, x_api_secret, x_access_token, x_access_token_secret)
    except Exception as e:
        logging.error("Erreur de connexion à l'API V2 de X: %s", e)
        return
    tag = get_network_tag(engine, 'X')
    for post in posts:
        if post.article_image_url != "images/no_picture.jpg": # Article ayant une image
            media_id = [] # Pas d'image  uploader
            success, network_post_id = post_to_x(x_apiv2, post, tag, media_id)
        elif post.image_url != "": # Article sans image, post avec image uploadée 
            media_id = [upload_image_to_x(x_api_key, x_api_secret, x_access_token, x_access_token_secret, post.image_url)]
            success, network_post_id = post_to_x(x_apiv2, post, tag, media_id)
        else:
            success = False      
        if success:
            modify_status(engine, post['post_id'], post['title'])
            network_post_link = x_url + network_post_id
            update_network_post_id(engine, post['post_id'], network_post_link)
        else:
            logging.error("Changement de statut impossible %s", post['title'])

# def clean_and_resize_image(image_bytes, max_size=1000000):
#     """
#     Supprime les métadonnées et réduit la taille de l'image si nécessaire.
#     Retourne les bytes de l'image nettoyée, ou None si impossible.
#     """
#     img = Image.open(io.BytesIO(image_bytes))
#     # Convertir en RGB pour éviter les problèmes de mode
#     if img.mode in ("RGBA", "P"):
#         img = img.convert("RGB")
#     quality = 95
#     while True:
#         buffer = io.BytesIO()
#         img.save(buffer, format="JPEG", quality=quality, optimize=True)
#         data = buffer.getvalue()
#         if len(data) <= max_size or quality < 30:
#             break
#         quality -= 5  # Réduire la qualité pour compresser
#     if len(data) > max_size:
#         # Dernier recours : redimensionner l'image
#         width, height = img.size
#         while len(data) > max_size and width > 100 and height > 100:
#             width = int(width * 0.9)
#             height = int(height * 0.9)
#             img = img.resize((width, height), Image.LANCZOS)
#             buffer = io.BytesIO()
#             img.save(buffer, format="JPEG", quality=quality, optimize=True)
#             data = buffer.getvalue()
#     if len(data) > max_size:
#         return None  # Impossible de réduire suffisamment
#     return data

def post_to_bluesky(post, client_bluesky, tag):
    image_url = post['image_url']
    if post.article_image_url != 'images/no_picture.jpg':
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type')
            if content_type not in ['image/jpeg', 'image/png']:
                logging.error("Erreur : Le type de contenu attendu est" \
                " 'image/jpeg' ou 'image/png', mais reçu %s", content_type)
                return
            img_data=response.content
            logging.info("Upload de l'image Bluesky OK %s", post['title'])
        except requests.exceptions.HTTPError as err:
            logging.error("Erreur HTTP lors de la lecture de image_url : %s", err)
            return
    else: # Récupérer l'image en local
        image_path = "static/" + image_url
        try:
            with open(image_path, 'rb') as image_file:
                img_data = image_file.read()
        except Exception as e:
            logging.error("Erreur lors du load de l'image %s : %s", image_url), e
    if post['link'] != '':
        # Création et upload d'une WebSite Card
        thumb = client_bluesky.upload_blob(img_data)
        url_to_post = post['link'] + tag
        logging.info("URL Bluesky : %s", url_to_post)
        embed = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=post['title'],
                description=post['description'],
                uri=url_to_post,
                thumb=thumb.blob
            )
        )
        try:
            response = client_bluesky.send_post(post['tagline'], embed=embed)
            network_post_id = response.uri.rsplit('/', 1)[1]
            logging.info("Post %s posté sur Bluesky  URI = %s", post['title'], network_post_id)
            return network_post_id
        except Exception as err:
            logging.info("Échec de publication sur Bluesky de %s - %s", post['title'], err)
            return None
    else:
        # Upload d'un post créé avec une image (pas de post['link'])
        try:
            #img_data_clean = clean_and_resize_image(img_data, max_size=900000)
            #if img_data_clean is None:
            #    logging.error("Impossible de réduire l'image sous 1 Mo pour %s", post['title'])
            #    return
#            response = client_bluesky.send_image(text=post['tagline'], image=img_data_clean, image_alt='')
            response = client_bluesky.send_image(text=post['tagline'], image=img_data, image_alt='')
            network_post_id = response.uri.rsplit('/', 1)[1]
            logging.info("Post posté sur Bluesky : %s, %s", post['tagline'], network_post_id)
            return network_post_id
        except Exception as err:
            logging.info("Échec de publication sur Bluesky de %s - %s", post['tagline'], err)
            return None

def post_all_bluesky(posts, engine, newspaper):
    bluesky_login = os.getenv('BLUESKY_LOGIN_'+newspaper.upper())
    bluesky_password = os.getenv('BLUESKY_PASSWORD_'+newspaper.upper())
    bluesky_url = os.getenv('BLUESKY_URL_'+newspaper.upper())
    tag = get_network_tag(engine, 'Bluesky')
    client_bluesky = Client()
    try:
        client_bluesky.login(bluesky_login, bluesky_password)
        logging.info("Connexion réussie à Bluesky")
    except Exception as err:
        logging.info("Échec de connexion à Bluesky %s", err)
        return
    tag = get_network_tag(engine, 'Bluesky')
    for post in posts:
        network_post_id = post_to_bluesky(post, client_bluesky, tag)
        if network_post_id is not None:
            network_post_link = bluesky_url+str(network_post_id)
            update_network_post_id(engine, post['post_id'], network_post_link)
            modify_status(engine, post['post_id'], post['tagline'])

###### Fonctions de fetch_rss
def fetch_rss(url: str) -> list:
    """
    Récupère les entrées du flux RSS QDM/QPH à partir d'une URL donnée.

    Args:
        url (str): L'URL du flux RSS.

    Returns:
        list: Une liste des entrées du flux RSS, ou None en cas d'erreur.
    """
    logging.debug("Début d'import RSS %s", url)
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            raise ValueError(feed.bozo_exception)
        logging.debug("Lecture du flux RSS réussie %s", url)
        return feed.entries
    except Exception as e:
        logging.error('Lecture du flux RSS impossible : %s', e)
        return None

def is_valid_article(item: str) -> boolean:
    if item.title == 'Votre journal au format numérique':
        return False
    else:
        return True

def normalize_spaces(text):
    return ' '.join(text.split())

def convert_date(date_str):
    return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')

def fetch_article_html(url: str):
    try:
        http_response = requests.get(url, timeout=10)
        html_article = bs(http_response.text, 'html.parser')
        return html_article
    except requests.exceptions.RequestException as e:
        logging.error("Échec lors de la lecture URL %s : %s", url, e)

def get_article_nid(html_article):
        # <article data-history-node-id="248526"
        try:
            nid_article = html_article.article['data-history-node-id']
            logging.debug("NID : %s", nid_article)
            return nid_article
        except Exception:
            logging.error("Pas de NID pour l'article")
            return None

def is_article_in_db(session, nid_article):
    stmt = (select(Articles_rss)
                     .where(Articles_rss.nid == nid_article)
            )  
    article_in_db = session.execute(stmt).scalars().first()
    logging.debug("Article in db : %s", article_in_db)
    return article_in_db

def extract_article_data(html_article, nid_article, pubdate, newspaper):
    new_article = {}
    new_article['nid'] = nid_article
    new_article['title'] = html_article.find('meta', attrs = {"name":"twitter:title"}).attrs['content']
    new_article['link'] = html_article.find('meta', attrs = {"name":"twitter:url"}).attrs['content']
    new_article['summary'] = html_article.find('meta', attrs = {"name":"twitter:description"}).attrs['content']
    image_meta = html_article.find('meta', attrs={"name": "twitter:image"})
    if image_meta is not None:
        try:
            new_article['image_url'] = image_meta['content']
        except KeyError:  # L'attribut 'content' n'existe pas
            new_article['image_url'] = "images/no_picture.jpg"
    else:
        new_article['image_url'] = "images/no_picture.jpg"
    new_article['pubdate'] = convert_date(pubdate)
    new_article['online'] = 1
    new_article['newspaper'] = newspaper
    return new_article
    
def store_new_article(session, new_article) -> boolean:
    new_article_db = Articles_rss(title=normalize_spaces(new_article['title']),
                                  nid=new_article['nid'],
                                  link=new_article['link'],
                                  summary=new_article['summary'],
                                  image_url=new_article['image_url'],
                                  pubdate=new_article['pubdate'],
                                  online=new_article['online'],
                                  newspaper=new_article['newspaper'])
    try:
        session.add(new_article_db)
        session.commit()
        return True
    except SQLAlchemyError as err:
        session.rollback()
        logging.error("Impossible d'enregistrer l'article %s", err)
        return False

def update_article(session, new_article):
    stmt = (select(Articles_rss)
            .where(Articles_rss.nid==new_article['nid'])
            )
    try:
        article = session.scalars(stmt).one()
        logging.debug("Article à mettre à jour : %s", article.title)
        try:
            article.title = normalize_spaces(new_article['title'])
            article.link = new_article['link']
            article.summary = new_article['summary']
            article.image_url=new_article['image_url']
            article.pubdate = new_article['pubdate']
            article.online=new_article['online']
            session.commit()
            logging.debug("Article mis à jour : %s", article.title)
        except SQLAlchemyError as err:
            logging.error("Erreur de mise à jour de l'article en base : %s", err)
            session.rollback()
    except SQLAlchemyError as err:
        logging.error("Erreur de mise à jour de l'article en base : %s", err)

def load_articles(engine, newspaper, url_rss):
#    URL_RSS = os.getenv('QDM_URL_RSS')
    feed = fetch_rss(url_rss)
    if feed:
        nb_itemrss = 0
        for itemrss in feed:
            if is_valid_article(itemrss):
                html_article = fetch_article_html(itemrss.link)
                nid_article = get_article_nid(html_article)
                if nid_article is not None:
                    try:
                        with get_session(engine) as session:
                            new_article = extract_article_data(html_article, nid_article, itemrss.published, newspaper)
                            if is_article_in_db(session, nid_article) is None:
                                article_stored = store_new_article(session, new_article)
                                if article_stored:
                                    logging.debug("Article stocké : new_article['title]")
                                else:
                                    logging.error("Article impossible à stocker : new_article['title']")
                            else: # Remplacement de l'article déjà en base
                                update_article(session, new_article)
                                logging.debug("Article déjà en base")

                    except Exception as err:
                        logging.error("Pb lors du stockage d'un nouvel article : %s", err)
                else:
                    logging.error("NID absent dans l'article")
            else:
                logging.debug("Article invalide %s", itemrss.title)
            nb_itemrss += 1
            if nb_itemrss == 25: # nombre d'articles à traiter dans le flux RSS
                break

def post_auto_function(engine, newspaper):
    networks = ['X', 'Bluesky'] # Active networks
    logging.info("Traitement de posts %s", newspaper)
    for network in networks:
        posts = fetch_posts(engine, network, newspaper)
        if posts != []:
            if network == 'X':
                post_all_x(posts, engine, newspaper)
            elif network == 'Bluesky':
                post_all_bluesky(posts, engine, newspaper)
        else:
            logging.info("Aucun post %s sur %s", network, newspaper)
    logging.info("Fin traitement de posts %s", newspaper)

###### MAIN
def main():
    #load_dotenv(dotenv_path='/Users/stephanelong/Documents/DEV/Medpost/fetch_post/.env')
    log_path = os.getenv('LOG_PATH')
    database_path = os.getenv('DATABASE_PATH')
    url_newspapers = {'qdm': os.getenv('QDM_URL_RSS'), 'qph':os.getenv('QPH_URL_RSS')}
#    url_newspapers = {'qdm': '/app/rss.xml', 'qph':os.getenv('QPH_URL_RSS')}
    logging.basicConfig(filename=log_path,
                        encoding='utf-8',
                        level=logging.DEBUG,
                        format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M'
                        )
    engine = create_db_and_tables(database_path)
    for newspaper, url_newspaper in url_newspapers.items():
        load_articles(engine, newspaper, url_newspaper)
        post_auto_function(engine, newspaper)

if __name__ == '__main__':
    main()
