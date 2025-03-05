import feedparser
import logging
from datetime import datetime
from sqlalchemy import create_engine, select, exists, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session

URL_DB = '/Users/stephanelong/Documents/DEV/postX/flask/rss_qdm.db'
engine = create_engine(f'sqlite:///{URL_DB}') #, echo=True
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
         return f"Post X {self.content} - {self.date_pub}"

class Networks(Base):
     __tablename__ = 'networks'
     id = Column(Integer, primary_key=True, autoincrement=True)
     name = Column(String, nullable=False)

     def __repr__(self):
         return f"Network {self.id} : {self.name}"

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

def main():
    logging.basicConfig(filename='/Users/stephanelong/Documents/DEV/postX/flask/postx.log',
                        encoding='utf-8',
                        level=logging.INFO,
                        format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M'
                        )
    Base.metadata.create_all(engine)
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

if __name__ == '__main__':
    main()
