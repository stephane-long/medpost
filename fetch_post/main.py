import logging
import os
from dotenv import load_dotenv
import requests
import tweepy
from datetime import datetime, timezone
from sqlalchemy import select, and_, update, exists
from sqlalchemy.orm import Session
import feedparser
from database import Base, Articles_rss, Posts, Networks, create_db_and_tables, get_session
from atproto import models, Client

###### Fonctions de post_auto

def fetch_posts(selectedfeed, engine):
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
                    .filter(and_(Networks.name == selectedfeed,
                                 Posts.status == 'plan',
                                 Posts.date_pub < datetime.today()))
                    )
        try:
            posts = session.execute(statement).mappings().all()
            logging.info(f'Lecture de {len(posts)} posts sur {selectedfeed}')
        except Exception as e:
            logging.error(f"Erreur de lecture des posts : {e}")
    return posts

def connect_x_apiv2(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET):
    return tweepy.Client(consumer_key=X_API_KEY,
                         consumer_secret=X_API_SECRET,
                         access_token=X_ACCESS_TOKEN,
                         access_token_secret=X_ACCESS_TOKEN_SECRET)

def download_images(posts, file_path):
    for post in posts:
        image_url = post['image_url']
        image_path = f"{file_path}image{post['article_id']}.jpg"
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type')
            if content_type not in ['image/jpeg', 'image/png']:
                logging.error(f"Erreur : Le type de contenu attendu est 'image/jpeg' ou 'image/png', mais reçu '{content_type}'")
                return
            with open(image_path, 'wb') as file:
                file.write(response.content)
            post['image_path'] = image_path
            logging.info(f"Image downloaded to {image_path}")
        except requests.exceptions.HTTPError as err:
            logging.error(f"Erreur HTTP : {err}")

def fetch_networks(engine):
    with get_session(engine) as session:
        statement = (select(Networks.name)
                    .join(Posts, Networks.id == Posts.network)
                    .filter(and_(Posts.status == 'plan',
                                 Posts.date_pub < datetime.now()))
                    .distinct())
        try:
            networks = session.scalars(statement).all()
        except Exception as e:
            logging.error('Erreur dans la collecte des réseaux')
            networks = []
        return networks

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
            logging.info(f"Mise à jour du network_post_id {network_post_id} pour le post {post_id}")
        except Exception as e:
            session.rollback()
            logging.error(f"Erreur lors de la mise à jour du network_post_id pour le post {post_id}: {e}")

def modify_status(engine, post_id, post_title):
    logging.info(f"Réception modify_stats : {post_id}")
    with get_session(engine) as session:
        try:
            statement = (update(Posts).
                         where(Posts.id == post_id)
                         .values(status='pub')
            )
            session.execute(statement)
            session.commit()
            logging.info(f"Mise à jour du statut de publication de {post_title}")
        except Exception as e:
            logging.error(f"Erreur {e} lors de modification du status post {post_title} ")

def post_to_x(api, post):
    post_content = f"{post['title']} {post['link']}"
    try:
        response = api.create_tweet(text=post_content)
        network_post_id = response.data['id']
        logging.info(f"Tweet publié avec l'ID : {network_post_id} - Link = {post['link']}")
        return True, network_post_id
    except Exception as e:
        logging.error(f"Échec du post: {e}\n{post_content}")
        return False, None


def post_all_x(posts, engine):
#    load_dotenv()
    X_API_SECRET = os.getenv('API_KEY_SECRET')
    X_API_KEY = os.getenv('API_KEY')
    X_ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
    X_ACCESS_TOKEN_SECRET= os.getenv('ACCESS_TOKEN_SECRET')
    X_URL_QDM = os.getenv('X_URL_QDM')
    # Connexion à X API V2
    try:
        x_apiv2 = connect_x_apiv2(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)
        logging.info("Connexion à l'API V2 de X")
    except Exception as e:
        logging.error(f"Erreur de connexion à l'API V2 de X: {e}")
        return
    for post in posts:
        success, network_post_id = post_to_x(x_apiv2, post)
        if success:
            modify_status(engine, post['post_id'], post['title'])
            network_post_link = X_URL_QDM + network_post_id
            update_network_post_id(engine, post['post_id'], network_post_link)
        else:
            logging.error(f"Changement de statut impossible {post['title']}")

def post_to_bluesky(post, client_bluesky):
    # Download image from image_url
    try:
        image_url = post['image_url']
        response = requests.get(image_url)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type')
        if content_type not in ['image/jpeg', 'image/png']:
            logging.error(f"Erreur : Le type de contenu attendu est 'image/jpeg' ou 'image/png', mais reçu '{content_type}'")
            return
    except requests.exceptions.HTTPError as err:
        logging.error(f"HTTP error while reading image_url : {err}")
        return
    # upload image to Bluesky
    img_data=response.content
    thumb = client_bluesky.upload_blob(img_data)
    # Creating the web card and uploading
    embed = models.AppBskyEmbedExternal.Main( 
        external=models.AppBskyEmbedExternal.External(
            title=post['title'],
            description=post['description'],
            uri=post['link'],
            thumb=thumb.blob
        )
    )
    web_card = client_bluesky.send_post(post['tagline'], embed=embed)
    network_post_id = web_card.uri.rsplit('/', 1)[1]
    return network_post_id

def post_all_bluesky(posts, engine):
    BLUESKY_LOGIN = os.getenv('BLUESKY_LOGIN')
    BLUESKY_PASSWORD = os.getenv('BLUESKY_PASSWORD')
    BLUESKY_URL_QDM = os.getenv('BLUESKY_URL_QDM')
    client_bluesky = Client()
    logging.info(f"Paramètres Bluesky {BLUESKY_LOGIN} {BLUESKY_PASSWORD}")
    try:
        client_bluesky.login(BLUESKY_LOGIN, BLUESKY_PASSWORD)
        logging.info("Connexion réussie à Bluesky")
    except Exception as err:
        logging.info(f"Échec de connexion à Bluesky {err}")
        return
    for post in posts:
        network_post_id = post_to_bluesky(post, client_bluesky)
        network_post_link = BLUESKY_URL_QDM+str(network_post_id)
        update_network_post_id(engine, post['post_id'], network_post_link)
        logging.info(f"Post {post['title']} posté sur Bluesky --- URI = {network_post_id}")
        modify_status(engine, post['post_id'], post['title'])

###### Fonctions de fetch_rss
def fetch_rss(url):
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            raise ValueError(feed.bozo_exception)
        logging.info('Lecture du flux RSS réussie')
        return feed.entries
    except Exception as e:
        logging.error(f'Lecture du flux RSS impossible : {e}')
        return None

def check_itemrss(item):
    if item.title == 'Votre journal au format numérique': # article à ne pas poster
        logging.info(f'Article supprimé : {item.title}')
        return False, None
    try:
        image_url = item.links[1].href # teste si paramètre vignette présent sinon vignette URL = NULL
    except IndexError:
        logging.info('Pas d\'image')
        image_url = None
    return True, image_url

def itemrss_ispresent(session, title):
    stmt = select(exists().where(Articles_rss.title == title))
    result = session.execute(stmt).scalar()
    return result

def convert_date(date_str):
    return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')

def fetch_rss_function(engine):
    url_rss = 'https://www.lequotidiendumedecin.fr/rss.xml'
    feed_qdm = fetch_rss(url_rss)
    if feed_qdm:
        logging.info('Lecture des articles RSS')
        nb_itemrss = 0
        for itemrss in feed_qdm:
            item_valid, image_url = check_itemrss(itemrss)
            if item_valid:
                try:
                    pubdate = convert_date(itemrss.published)
                    with get_session(engine) as session:
                        present = itemrss_ispresent(session, itemrss.title)
                        if not present:
                            new_article = Articles_rss(title=itemrss.title, link=itemrss.link, summary=itemrss.summary , image_url=image_url , pubdate=pubdate, statut=1)
                            session.add(new_article)
                            session.commit()
                            nb_itemrss += 1
                except Exception as inst:
                    logging.error(f'Erreur lors de la lecture d\'un item RSS: {inst}')
        logging.info(f'{nb_itemrss} nouveaux articles insérés')
        print(f"{nb_itemrss} nouveaux articles insérés")

def post_auto_function(engine):
    image_path = os.getenv('IMAGES_PATH') 
    networks = fetch_networks(engine)
    print(f"réseaux référencés : {networks}")

    for network in networks:
        posts = fetch_posts(network, engine)
        # download_images(posts, image_path)
        if network == 'X':
            pass
            post_all_x(posts, engine)
        elif network == 'Bluesky':
            post_all_bluesky(posts, engine)
    logging.info("Fin publication des posts")

###### MAIN
def main():
    #load_dotenv(dotenv_path='/Users/stephanelong/Documents/DEV/Medpost/fetch_post/.env')
    log_path = os.getenv('LOG_PATH')
    database_path = os.getenv('DATABASE_PATH')
    logging.basicConfig(filename=log_path,
                        encoding='utf-8',
                        level=logging.INFO,
                        format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M'
                        )

    engine = create_db_and_tables(database_path)
    fetch_rss_function(engine)
    post_auto_function(engine)

if __name__ == '__main__':
    main()
