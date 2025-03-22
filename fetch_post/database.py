# /Users/stephanelong/Documents/DEV/Medpost/fetch_post/database.py

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
import os

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
    statut = Column(Integer, nullable=False)

    def __repr__(self):
        return f"Article {self.title} - {self.pubdate}"

class Posts(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    tagline = Column(String, nullable=False)
    image_url = Column(String)
    date_pub = Column(DateTime, nullable=False)
    status = Column(String, nullable=False)
    network_post_id = Column(Integer, nullable=True)
    id_article = Column(ForeignKey('articles_rss.id'))
    network = Column(ForeignKey('networks.id'))


    def __repr__(self):
        return f"Post sur {self.network} - {self.content} - {self.date_pub}"

class Networks(Base):
    __tablename__ = 'networks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tag = Column(String, nullable=True)

    def __repr__(self):
        return f"Network {self.id} : {self.name}"

# Function to create the engine and the session
def create_db_and_tables(database_path):
    engine = create_engine(f'sqlite:///{database_path}')
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()