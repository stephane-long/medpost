import logging
import os
from dotenv import load_dotenv
import requests
import tweepy
from datetime import datetime, timezone
from sqlalchemy import select, and_, update, exists
from sqlalchemy.orm import Session
import feedparser
# Database module
from database import Base, Articles_rss, Posts, Networks, create_db_and_tables, get_session

###### Fonctions de post_auto
def build_posts_dic(posts):
    return [
        {
            'content': post[0],
            'image_url': post[1],
            'link': post[3],
            'article_id': post[2],
            'post_id': post[5]
        }
        for post in posts
    ]

def fetch_posts(selectedfeed, engine):
    with get_session(engine) as session:
        statement = (select(Posts.content,
                            Posts.image_url,
                            Articles_rss.id,
                            Articles_rss.link,
                            Networks.name,
                            Posts.id)
                    .join(Articles_rss, Articles_rss.id == Posts.id_article)
                    .join(Networks, Networks.id == Posts.network)
                    .filter(and_(Networks.name == selectedfeed,
                                 Posts.status == 'plan',
                                 Posts.date_pub < datetime.today()))
                    )
        try:
            posts = session.execute(statement).all()
            posts_dic = build_posts_dic(posts)
            logging.info(f'Lecture de {len(posts)} posts sur {selectedfeed}')
        except Exception as e:
            logging.error(f"Erreur de lecture des posts : {e}")
            posts_dic = {}
    return posts_dic

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
        print(f"DATE {datetime.today()} - {datetime.now()}")
        try:
            networks = session.scalars(statement).all()
        except Exception as e:
            logging.error('Erreur dans la collecte des réseaux')
            networks = []
        return networks

    

def post_to_x(api, post):
    post_content = f"{post['content']} {post['link']}"
    try:
        response = api.create_tweet(text=post_content)
        logging.info(f"Tweet publié avec l'ID : {response.data['id']} - Link = {post['link']}")
        return True
    except Exception as e:
        logging.error(f"Échec du post: {e}\n{post_content}")
        return False

def modify_status(post, engine):
    statement = update(Posts).where(Posts.id == post['post_id']).values(status='pub')
    with get_session(engine) as session:
        try:
            session.execute(statement)
            session.commit()
            logging.info(f"Mise à jour du statut de publication de {post['link']}")
        except Exception as e:
            logging.error(f"Erreur {e} lors de modification du status post {post['link']} ")

def post_all_x(posts, engine):
#    load_dotenv()
    X_API_SECRET = os.getenv('API_KEY_SECRET')
    X_API_KEY = os.getenv('API_KEY')
    X_ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
    X_ACCESS_TOKEN_SECRET= os.getenv('ACCESS_TOKEN_SECRET')
    # Connexion à X API V2
    try:
        x_apiv2 = connect_x_apiv2(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)
        logging.info("Connexion à l'API V2 de X")
    except Exception as e:
        logging.error(f"Erreur de connexion à l'API V2 de X: {e}")
        return
    for post in posts:
        success = post_to_x(x_apiv2, post)
        if success:
            modify_status(post, engine)
        else:
            logging.error(f"Changement de statut impossible {post.content}")


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

    # Create the db engine and tables
    engine = create_db_and_tables(database_path)

    # Fetch RSS
    fetch_rss_function(engine)

    # Post auto
    post_auto_function(engine)

if __name__ == '__main__':
    main()
