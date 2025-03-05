import logging
import os
from dotenv import load_dotenv
import requests
import tweepy
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy import create_engine, select, and_, Column, Integer, String, DateTime, ForeignKey, update, exists
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
import feedparser

###### DATABASE
load_dotenv()
URL_DB = os.getenv('DATABASE_PATH')
engine = create_engine(f'sqlite:///{URL_DB}')

class Base(DeclarativeBase):
    pass

class Articles_rss(Base):
    __tablename__ = 'articles_rss'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    link = Column(String, nullable=False)
    summary = Column(String)
    image_url = Column(String)
    pubdate = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"Article {self.title} - {self.pubdate}"

class Posts(Base):
    __tablename__ = 'Posts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String, nullable=False)
    image_url = Column(String)
    date_pub = Column(DateTime, nullable=False)
    status = Column(String, nullable=False)
    id_article = Column(ForeignKey('articles_rss.id'))
    network = Column(ForeignKey('networks.id'))

    def __repr__(self):
        return f"Post sur {self.network} - {self.content} - {self.date_pub}"

class Networks(Base):
    __tablename__ = 'networks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)

    def __repr__(self):
        return f"Network {self.id} : {self.name}"
###### FIN DATABASE

###### Fonctions de post_auto
def build_posts_dic(posts):
    posts_dic = []
    for post in posts:
        post_dic = {
            'content': post[0],
            'image_url': post[1],
            'link': post[3],
            'article_id': post[2],
            'post_id': post[5]
        }
        posts_dic.append(post_dic)
    return posts_dic

def fetch_posts(selectedfeed):
    with Session(engine) as session:
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
    x_apiv2 = tweepy.Client(consumer_key=X_API_KEY,
                        consumer_secret=X_API_SECRET,
                        access_token=X_ACCESS_TOKEN,
                        access_token_secret=X_ACCESS_TOKEN_SECRET)
    return x_apiv2

def download_images(posts, file_path):
    for post in posts:
        image_url = post['image_url']
        image_path = "".join([file_path, "image", str(post['article_id']), '.jpg'])
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type')
            if (content_type != 'image/jpeg') & (content_type != 'image/png'):
                print(f"Erreur : Le type de contenu attendu est 'image/jpeg', mais reçu '{content_type}'")
                return
            with open(image_path, 'wb') as file:
                file.write(response.content)
            post['image_path'] = image_path
            print(f"Image downloaded to {image_path}")
        except requests.exceptions.HTTPError as err:
            if response.status_code == 400:
                print("Erreur 400 : Bad Request")
            else:
                print(f"Erreur HTTP : {err}")

def fetch_networks():
    with Session(engine) as session:
        statement = (select(Networks.name)
                    .join(Posts, Networks.id == Posts.network)
                    .filter(and_(Posts.status == 'plan',
                                 Posts.date_pub < datetime.today()))
                    .distinct())
        try:
            networks = session.scalars(statement).all()
        except Exception as e:
            logging.error('Erreur dans la collecte des réseaux')
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

def modify_status(post):
    statement = update(Posts).where(Posts.id == post['post_id']).values(status='pub')
    with Session(engine) as session:
        try:
            session.execute(statement)
            session.commit()
            logging.info(f"Mise à jour du statut de publication de {post['link']}")
        except Exception as e:
            logging.error(f"Erreur {e} lors de modification du status post {post['link']} ")

def post_all_x(posts):
    load_dotenv()
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
    for post in posts:
        success = post_to_x(x_apiv2, post)
        if success:
            modify_status(post)
        else:
            logging.error("Changement de statut annulé")


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
        print('Pas d\'image')
        image_url = None
    return True, image_url

def itemrss_ispresent(session, title):
    stmt = select(exists().where(Articles_rss.title == title))
    result = session.execute(stmt).scalar()
    print(f"Résultat du test d'existence : {result}")
    return result

def convert_date(date_str):
    pubdate = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
    return pubdate

def insert_networks(Session, networks):
    """ Insertion des réseaux si création de la table"""
    new_networks = [Networks(name=network) for network in networks]
    with Session(engine) as session:
        session.add_all(new_networks)
        session.commit()

def fetch_rss_function():
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
                    with Session(engine) as session:
                        present = itemrss_ispresent(session, itemrss.title)
                        if not present:
                            new_article = Articles_rss(title=itemrss.title, link=itemrss.link, summary=itemrss.summary , image_url=image_url , pubdate=pubdate)
                            session.add(new_article)
                            session.commit()
                            nb_itemrss += 1
                except Exception as inst:
                    logging.info(f'Erreur lors de la lecture d\'un item RSS: {inst}')
                    print(f'Erreur lors de la lecture d\'un item RSS: {inst}')
        logging.info(f'{nb_itemrss} nouveaux articles insérés')
        print(f"{nb_itemrss} nouveaux articles insérés")
        networks = ['X', 'LinkedIn', 'Bluesky', 'Facebook', 'Instagram', 'Thread']
        insert_networks(Session, networks)

def post_auto_function():
    image_path = os.getenv('IMAGE_PATH') 
    networks = fetch_networks()
    print(f"réseaux référencés : {networks}")

    for network in networks:
        posts = fetch_posts(network)
        # download_images(posts, image_path)
        if network == 'X':
            post_all_x(posts)
    logging.info("Fin publication des posts")

def main():
    log_path = os.getenv('LOG_PATH')
    logging.basicConfig(filename=log_path,
                        encoding='utf-8',
                        level=logging.INFO,
                        format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M'
                        )
    
    Base.metadata.create_all(engine)

    # Fetch RSS
    fetch_rss_function()

    # Post auto
    post_auto_function()

if __name__ == '__main__':
    main()