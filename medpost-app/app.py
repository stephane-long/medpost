import logging
import os
from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from sqlalchemy import select
from dotenv import load_dotenv
from datetime import datetime, timedelta
from requests import Session


app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/')

#load_dotenv(dotenv_path='.env.dev')
db_path = os.getenv('DATABASE_PATH')
log_path = os.getenv('LOG_PATH')
print(db_path, log_path, sep=' - ')

app.config['SECRET_KEY'] = 'APP_SECRET_KEY'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


logging.basicConfig(filename=log_path,
                    encoding='utf-8',
                    level=logging.INFO,
                    format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M'
                    )

########### DATABASE #################

class Articles_rss(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False, index=True)
    link = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    pubdate = db.Column(db.DateTime, nullable=False)
    statut = db.Column(db.Integer, nullable=False)


    def __repr__(self):
        return f"Article {self.title} - {self.pubdate}"

class Posts(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    tagline = db.Column(db.String, nullable=True)
    image_url = db.Column(db.String)
    date_pub = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String, nullable=False)
    network_post_id = db.Column(db.String, nullable=True)
    id_article = db.Column(db.ForeignKey('articles_rss.id'))
    network = db.Column(db.ForeignKey('networks.id'))

    def __repr__(self):
        return f"Post {self.title} - {self.date_pub}"

class Networks(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    tag = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"Network {self.id} - {self.name}"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(20), nullable=False)

########### FIN DATABASE #################

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_datetime_utils():
    def now_datetime():
        return datetime.now().isoformat(timespec='minutes')
    return {'current_datetime': now_datetime}

def fetch_articles(selectedfeed):
    if selectedfeed == 'qdm':
         articles = (db.session.query(Articles_rss)
                    .outerjoin(Posts, Articles_rss.id == Posts.id_article)
                    .filter(Posts.id_article == None)
                    .with_entities(Articles_rss.id,
                                    Articles_rss.title,
                                    Articles_rss.summary,
                                    Articles_rss.link,
                                    Articles_rss.image_url,                                       
                                    Articles_rss.pubdate
                                    )
                    .order_by(Articles_rss.pubdate.desc())
                    )
    else:
         subquery = (db.session.query(Articles_rss.id) # Articles postés sur selectedfeed
                     .join(Posts, Articles_rss.id == Posts.id_article)
                     .join(Networks, Posts.network == Networks.id)
                     .filter(Networks.name == selectedfeed)
                     .subquery())
         subquery_select = select(subquery)

         articles = (db.session.query(Articles_rss) 
                    .outerjoin(Posts, Articles_rss.id == Posts.id_article)
                    .outerjoin(Networks, Posts.network == Networks.id)
                    .filter(~Articles_rss.id.in_(subquery_select)) # On ne garde que les articles non postés sur selectdfeed
                    .with_entities(Articles_rss.id,
                                    Articles_rss.title,
                                    Articles_rss.summary,
                                    Articles_rss.link,
                                    Articles_rss.image_url,                                       
                                    Articles_rss.pubdate,
                                    Networks.name
                                   )
                    .order_by(Articles_rss.pubdate.desc())
                    )
         nb = (db.session.query(Posts)
               .outerjoin(Networks, Posts.network==Networks.id)
               .filter(Networks.name==selectedfeed)
               .count()
               )
    return articles

def fetch_pub_posts(selectedfeed):
    if selectedfeed == 'qdm':
        articles = (db.session.query(Posts)
                    .outerjoin(Articles_rss, Posts.id_article==Articles_rss.id)
                    .outerjoin(Networks, Posts.network==Networks.id)
                    .filter(Posts.status == 'pub')
                    .with_entities(Posts.id,
                                   Posts.title,
                                   Posts.description,
                                   Posts.tagline,
                                   Posts.image_url,
                                   Posts.date_pub,
                                   Posts.network_post_id,
                                   Networks.name
                                   )
                    .order_by(Posts.date_pub.desc())
                    .limit(5)
                    
                    )
    else:
                articles = (db.session.query(Posts)
                    .outerjoin(Articles_rss, Posts.id_article==Articles_rss.id)
                    .outerjoin(Networks, Posts.network==Networks.id)
                    .filter(Networks.name==selectedfeed)
                    .filter(Posts.status == 'pub')
                    .with_entities(Posts.id,
                                   Posts.title,
                                   Posts.description,
                                   Posts.tagline,
                                   Posts.image_url,
                                   Posts.date_pub,
                                   Posts.network_post_id,
                                   Networks.name
                                   )
                    .order_by(Posts.date_pub.desc())
                    .limit(5)
                                  )
    return articles

def fetch_planned_posts(selectedfeed):
    base_query = (db.session.query(Posts)
                .outerjoin(Articles_rss, Posts.id_article == Articles_rss.id)
                .outerjoin(Networks, Posts.network == Networks.id)
                .with_entities(Posts.id,
                            Posts.title,
                            Posts.description,
                            Posts.tagline,
                            Posts.image_url,
                            Posts.date_pub,
                            Articles_rss.link,
                            Networks.name)
                .order_by(Posts.date_pub.asc())
                )

    if selectedfeed == 'qdm':
        articles = (base_query
                   .filter(Posts.status == 'plan'))
    else:
        articles = (base_query
                   .filter(Networks.name == selectedfeed)
                   .filter(Posts.status == 'plan'))
    return articles

def record_new_post(article_id, image_url, title, description, tagline, post_datetime, networks):
    date_pub = datetime.strptime(post_datetime, '%Y-%m-%dT%H:%M')
    # Création d'un post par réseau sélectionné 
    for network_txt in networks: 
        network = (db.session.query(Networks.id)
               .filter(Networks.name==network_txt).first())
        new_post = Posts(
            title=title,
            description=description,
            tagline=tagline,
            image_url=image_url,
            date_pub=date_pub,
            status='plan',
            id_article=article_id,
            network=network.id
            )
        db.session.add(new_post)
        db.session.commit()
        logging.info(f"Nouveau post sur {network_txt} : {new_post.title}")

def update_post(post_id, title, description, tagline, post_datetime, network):
    date_plan = datetime.strptime(post_datetime, '%Y-%m-%dT%H:%M')
    post_to_modify = db.session.execute(db.select(Posts).filter_by(id=post_id)).scalar_one()
    post_to_modify.title = title
    post_to_modify.descripion = description
    post_to_modify.tagline = tagline
    post_to_modify.date_pub = date_plan
    post_to_modify.network = db.session.query(Networks.id).filter(Networks.name==network)
    db.session.commit()
    logging.info(f"Post MAJ sur {network} : {title}")

@app.route('/')
@app.route('/index')
@login_required
def home():
    perpage=7
    page = request.args.get('page', 1, type=int)
    selectedfeed = request.args.get('selectedfeed', 'qdm', type=str)
    articles = fetch_articles(selectedfeed)
    articles = articles.paginate(per_page=perpage, page=page)
    posts_pub = fetch_pub_posts(selectedfeed)
    posts_planned = fetch_planned_posts(selectedfeed)
    return render_template('index.html',
                            articles=articles,
                            posts_pub=posts_pub,
                            posts_planned=posts_planned,
                            selectedfeed=selectedfeed)

@app.route('/new_post', methods=['POST'])
@login_required
def new_post():
    article_id = request.form.get('article_id', type=int)
    image_url = request.form.get('image_url', type=str)
    selectedfeed = request.args.get('selectedfeed', type=str)
    title = request.form.get('title')
    description = request.form.get('description')
    tagline = request.form.get('tagline')
    link = request.form.get('link')
    post_datetime = request.form.get('datetime')
    networks = request.form.getlist('network')
    logging.info(f"Networks {networks}")
    if networks:
        record_new_post(article_id, image_url, title, description, tagline, post_datetime, networks)
    else:
        logging.info('Aucun post créé car aucun réseau')
    return redirect(url_for('home', selectedfeed=selectedfeed))

@app.route('/edit_post', methods=['POST'])
@login_required
def edit_post():
    post_id = request.form.get('post_id', type=int)
    selectedfeed = request.args.get('selectedfeed', type=str)
    title = request.form.get('post_title')
    description = request.form.get('post_description')
    tagline = request.form.get('post_tagline')
    link = request.form.get('post_link')
    post_datetime = request.form.get('post_datetime')
    network = request.form.get('post_network')
    update_post(post_id, title, description, tagline, post_datetime, network)
    return redirect(url_for('home', selectedfeed=selectedfeed))

@app.route('/delete_post')
@login_required
def delete_post():
    post_id = request.args.get('post_id', type=int)
    selectedfeed = request.args.get('selectedfeed', type=str)
    post = db.session.get(Posts, post_id)
    db.session.delete(post)
    db.session.commit()
    logging.info(f"Post supprimé : {post}")
    return redirect(url_for('home', selectedfeed=selectedfeed))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            logging.info(f"Connexion de {username}")
            return redirect(url_for('home'))
        else:
            return 'Invalid username or password'
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logging.info(f"Déconnexion de {current_user.username}")
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    #app.run(port=8000, debug=True)
    app.run(port=8000)