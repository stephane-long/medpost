import logging
import os
import re
# from dotenv import load_dotenv
from datetime import datetime
from xmlrpc.client import boolean
import requests
import tweepy
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
import feedparser
from database import Articles_rss, Posts, Networks, create_db_and_tables, get_session
from atproto import models, Client
from bs4 import BeautifulSoup as bs

###### Fonctions de post_auto

def fetch_posts(engine, selectedfeed, newspaper):
    with get_session(engine) as session:
        statement = (select(Posts.title,
                            Posts.description,
                            Posts.tagline,
                            Posts.image_url,
                            Articles_rss.id.label('article_id'),
                            Articles_rss.link,
                            Networks.name.label('network_name'),
                            Posts.id.label('post_id'))
                     .join(Articles_rss, Articles_rss.id == Posts.id_article)
                     .join(Networks, Networks.id == Posts.network)
                     .where(Networks.name == selectedfeed)
                     .filter(Posts.status == 'plan')
                     .filter(Posts.date_pub < datetime.today())
                     .filter(Articles_rss.newspaper == newspaper)
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

def post_to_x(api, post, tag):
    url_to_post = post['link'] + tag
    post_content = f"{post['title']} {url_to_post}"
    try:
        response = api.create_tweet(text=post_content)
        network_post_id = response.data['id']
        logging.info("Tweet publié - ID : %s Link : %s", network_post_id, url_to_post)
        return True, network_post_id
    except Exception as e:
        logging.error("Échec du post: %s\n%s", e, post_content)
        return False, None


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
        logging.info("Connexion à l'API V2 de X : %s", newspaper)
    except Exception as e:
        logging.error("Erreur de connexion à l'API V2 de X: %s", e)
        return
    tag = get_network_tag(engine, 'X')
    for post in posts:
        success, network_post_id = post_to_x(x_apiv2, post, tag)
        if success:
            modify_status(engine, post['post_id'], post['title'])
            network_post_link = x_url + network_post_id
            update_network_post_id(engine, post['post_id'], network_post_link)
        else:
            logging.error("Changement de statut impossible %s", post['title'])

def post_to_bluesky(post, client_bluesky, tag):
    # Download image from image_url
    try:
        image_url = post['image_url']
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type')
        if content_type not in ['image/jpeg', 'image/png']:
            logging.error("Erreur : Le type de contenu attendu est" \
            " 'image/jpeg' ou 'image/png', mais reçu %s", content_type)
            return
        logging.info("Upload de l'image Bluesky OK %s", post['title'])
    except requests.exceptions.HTTPError as err:
        logging.error("Erreur HTTP lors de la lecture de image_url : %s", err)
        return
    # upload image to Bluesky
    img_data=response.content
    thumb = client_bluesky.upload_blob(img_data)
    # Creating the web card and uploading
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
        web_card = client_bluesky.send_post(post['tagline'], embed=embed)
        network_post_id = web_card.uri.rsplit('/', 1)[1] # get the post id to build the post URL
        logging.info("Post %s posté sur Bluesky  URI = %s", post['title'], network_post_id)
        return network_post_id
    except Exception as err:
        logging.info("Échec de publication sur Bluesky de %s - %s", post['title'], err)
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
        try:
            network_post_id = post_to_bluesky(post, client_bluesky,
                                               tag) # need the network_post_id to build the post URL
        except Exception as err:
            logging.info("Echec de passage à post Bluesky : %s", err)
            break
        network_post_link = bluesky_url+str(network_post_id)
        update_network_post_id(engine, post['post_id'], network_post_link)
        modify_status(engine, post['post_id'], post['title'])

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

def extract_base_link(link):
    return re.sub(r"-\d$", '', link)

def itemrss_ispresent(session, title, link, newspaper):
    """
    Vérifie la présence d'un article du flux rss dans la BDD
           
    Args:
        session (_type_): session SQLalchemy
        title (str): titre à vérifier
        link (str): lien à vérifier
        newspaper (str): journal à tester

    Returns:
        boolean : True si article présent dans la BDD
    """
    normalized_title = normalize_spaces(title) # On se débarrasse des insécables
    stmt = (select(Articles_rss)
                  .where(Articles_rss.title == normalized_title)
                  .where(Articles_rss.newspaper == newspaper)
                )
    try:
        same_title = session.execute(stmt).scalars().all()
    except SQLAlchemyError as err:
        logging.debug("Erreur sql : %s", err)
        # En cas d'erreur, on n'ajoute pas l'article dansla base
        return True

    # pas d'article similaire dans la base
    if not same_title:
        logging.debug("Pas de doublon dans la base : %s", same_title)
        return False
    # Examen des articles ayant le même titre et même journal
    # Examen des liens
    for article in same_title:
        if article.link == link:
            # Liens identiques, il y a au moins un artcile similaire
            return True
        if extract_base_link(article.link) == extract_base_link(link):
            # Pas de doublon, on vérifie les autres articles ayant le même titre
            continue
        # Liens différents, il y a au moins un artcile similaire
        return True
    return False


def convert_date(date_str):
    return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')

def clean_text(text):
    """On se débarrase des balises p et br 
    présentes dans les summary des articles.

    Args:
        text (str): summary à nettoyer

    Returns:
        str: summary nettoyé
    """
    return re.sub(r"<[p/(br)].*?>", '', text)

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

    #     response['title'] = soup.find('meta', attrs = {"name":"twitter:title"}).attrs['content']
    #     try:
    #         response['image_url'] = soup.find('meta', attrs = {"name":"twitter:image"}).attrs['content']
    #     except Exception: # Pas de vignette dans la Twitter card du site
    #         response['image_url'] = "images/no_picture.jpg"
    #     response['summary'] = soup.find('meta', attrs = {"name":"twitter:description"}).attrs['content']
    #     response['link'] = soup.find('meta', attrs = {"name":"twitter:url"}).attrs['content']
    #     response['pubdate'] = datetime.now().replace(second=0, microsecond=0)
    #     return response
    # except re.exceptions.RequestException as e:
    #     logging.error("Échec lors de la lecture URL %s : %s", url, e)
    #     response['message'] = f"Erreur d'URL {url}"
    #     return response

def is_article_in_db(session, nid_article):
    stmt = (select(Articles_rss)
                     .where(Articles_rss.nid == nid_article)
            )  
    article_in_db = session.execute(stmt).scalars().first()
    logging.debug("Article in db : %s", article_in_db)
    return article_in_db

def read_new_article_html(html_article, nid_article, pubdate, newspaper):
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
    
def store_new_article(session, new_article):
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
                            if is_article_in_db(session, nid_article) is None:
                                new_article = read_new_article_html(html_article, nid_article, itemrss.published, newspaper)
                                if store_new_article(session, new_article):
                                    logging.debug("Article stocké : new_article['title]")
                                else:
                                    logging.error("Article impossible à stocker : new_article['title']")
                            else:
                                logging.debug("Article déjà en base")
                    except Exception as err:
                        logging.error("Pb lors du stockage d'un nouvel article : %s", err)
            else:
                logging.debug("Article invalide %s", itemrss.title)
            nb_itemrss += 1
            if nb_itemrss == 50:
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
        #post_auto_function(engine, newspaper)

if __name__ == '__main__':
    main()
