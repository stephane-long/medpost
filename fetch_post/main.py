import logging
import os
# from dotenv import load_dotenv
import requests
import tweepy
from datetime import datetime
from sqlalchemy import select, and_, update, exists
import feedparser
from database import Articles_rss, Posts, Networks, create_db_and_tables, get_session
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
            logging.info("Lecture de %s posts sur %s", len(posts), selectedfeed)
        except Exception as e:
            logging.error("Erreur de lecture des posts : %s", e)
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
                logging.error("Erreur : Le type de contenu attendu est 'image/jpeg' ou 'image/png', mais reçu %s", content_type)
                return
            with open(image_path, 'wb') as file:
                file.write(response.content)
            post['image_path'] = image_path
            logging.info("Image downloaded to %s", image_path)
        except requests.exceptions.HTTPError as err:
            logging.error("Erreur HTTP : %s", err)

def fetch_networks(engine):
    try:
        with get_session(engine) as session:
            statement = (select(Networks.name)
                        .join(Posts, Networks.id == Posts.network)
                        .filter(and_(Posts.status == 'plan',
                                    Posts.date_pub < datetime.now()))
                        .distinct())
            networks = session.scalars(statement).all()
    except Exception as err:
        logging.error("Erreur dans la collecte des réseaux : %s", err)
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
            logging.info("Mise à jour du network_post_id %s pour le post %s", network_post_id, post_id)
        except Exception as e:
            session.rollback()
            logging.error("Erreur lors de la mise à jour du network_post_id pour le post %s : %s", post_id, e)

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

def get_network_tag(network, engine):
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
        logging.info("Tweet publié avec l'ID : %s - Link = %s", network_post_id, url_to_post)
        return True, network_post_id
    except Exception as e:
        logging.error("Échec du post: %s\n%s", e, post_content)
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
        logging.error("Erreur de connexion à l'API V2 de X: %s", e)
        return
    tag = get_network_tag('X', engine)
    for post in posts:
        success, network_post_id = post_to_x(x_apiv2, post, tag)
        if success:
            modify_status(engine, post['post_id'], post['title'])
            network_post_link = X_URL_QDM + network_post_id
            update_network_post_id(engine, post['post_id'], network_post_link)
        else:
            logging.error("Changement de statut impossible %s", post['title'])

def post_to_bluesky(post, client_bluesky, tag):
    # Download image from image_url
    try:
        image_url = post['image_url']
        response = requests.get(image_url)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type')
        if content_type not in ['image/jpeg', 'image/png']:
            logging.error("Erreur : Le type de contenu attendu est 'image/jpeg' ou 'image/png', mais reçu %s", content_type)
            return
        logging.info("Upload image Bluesky OK %s", post['title'])
    except requests.exceptions.HTTPError as err:
        logging.error("HTTP error while reading image_url : %s", err)
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
        logging.info("Post {post['title']} posté sur Bluesky --- URI = %s", network_post_id)
        return network_post_id
    except Exception as err:
        logging.info("Échec de publication sur Bluesky de %s - %s", post['title'], err)
        return None

def post_all_bluesky(posts, engine):
    BLUESKY_LOGIN = os.getenv('BLUESKY_LOGIN')
    BLUESKY_PASSWORD = os.getenv('BLUESKY_PASSWORD')
    BLUESKY_URL_QDM = os.getenv('BLUESKY_URL_QDM')
    tag = get_network_tag('Bluesky', engine)
    client_bluesky = Client()
    try:
        client_bluesky.login(BLUESKY_LOGIN, BLUESKY_PASSWORD)
        logging.info("Connexion réussie à Bluesky")
    except Exception as err:
        logging.info("Échec de connexion à Bluesky %s", err)
        return
    tag = get_network_tag('Bluesky', engine)
    for post in posts:
        try:
            network_post_id = post_to_bluesky(post, client_bluesky, tag) # need the network_post_id to build the post URL
        except Exception as err:
            logging.info("Echec de passage à post Bluesky : %s", err)
            break
        network_post_link = BLUESKY_URL_QDM+str(network_post_id)
        update_network_post_id(engine, post['post_id'], network_post_link)
        modify_status(engine, post['post_id'], post['title'])

###### Fonctions de fetch_rss
def fetch_rss(url):
    logging.info("Début d'import RSS %s", url)
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            raise ValueError(feed.bozo_exception)
        logging.info('Lecture du flux RSS réussie')
        return feed.entries
    except Exception as e:
        logging.error('Lecture du flux RSS impossible : %s', e)
        return None

def check_itemrss(item):
    if item.title == 'Votre journal au format numérique': # article à ne pas poster
        logging.info('Article supprimé : %s', item.title)
        return False, None
    try:
        image_url = item.links[1].href # teste si paramètre vignette présent sinon vignette URL = NULL
    except IndexError:
        logging.info('Pas d\'image')
        image_url = None
    return True, image_url

def normalize_spaces(text):
    return ' '.join(text.split())

def itemrss_ispresent(session, title, newspaper):
    normalized_title = normalize_spaces(title)
    title_db = Articles_rss.title
    stmt = select(exists().where((title_db == normalized_title),
                                  (Articles_rss.newspaper == newspaper))
                                )
    result = session.execute(stmt).scalar()
    return result

def convert_date(date_str):
    return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')

def fetch_rss_function(engine, newspaper, url_rss):
#    URL_RSS = os.getenv('QDM_URL_RSS')
    feed_qdm = fetch_rss(url_rss)
    if feed_qdm:
        logging.info('Lecture des articles RSS %s', newspaper)
        nb_itemrss = 0
        for itemrss in feed_qdm:
            item_valid, image_url = check_itemrss(itemrss)
            if item_valid:
                try:
                    pubdate = convert_date(itemrss.published)
                    with get_session(engine) as session:
                        present = itemrss_ispresent(session, itemrss.title, newspaper)
                        if not present:
                            new_article = Articles_rss(title=normalize_spaces(itemrss.title), link=itemrss.link, summary=itemrss.summary , image_url=image_url , pubdate=pubdate, online=1, newspaper=newspaper)
                            session.add(new_article)
                            session.commit()
                            nb_itemrss += 1
                except Exception as inst:
                    logging.error('Erreur lors de la lecture d\'un item RSS: %s', inst)
        logging.info('%s nouveaux articles insérés', nb_itemrss)
        print(f"{nb_itemrss} nouveaux articles insérés")

def post_auto_function(engine):
    image_path = os.getenv('IMAGES_PATH')
    networks = fetch_networks(engine)
    for network in networks:
        posts = fetch_posts(network, engine)
        # download_images(posts, image_path)
        if network == 'X':
            post_all_x(posts, engine)
        elif network == 'Bluesky':
            post_all_bluesky(posts, engine)
    logging.info("Fin publication des posts")

###### MAIN
def main():
    #load_dotenv(dotenv_path='/Users/stephanelong/Documents/DEV/Medpost/fetch_post/.env')
    log_path = os.getenv('LOG_PATH')
    database_path = os.getenv('DATABASE_PATH')
    url_newspapers = {'QDM': os.getenv('QDM_URL_RSS'), 'QPH':os.getenv('QPH_URL_RSS')}
    logging.basicConfig(filename=log_path,
                        encoding='utf-8',
                        level=logging.INFO,
                        format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M'
                        )

    engine = create_db_and_tables(database_path)
    for newspaper, url_newspaper in url_newspapers.items():
        fetch_rss_function(engine, newspaper, url_newspaper)
#        post_auto_function(engine)

if __name__ == '__main__':
    main()
