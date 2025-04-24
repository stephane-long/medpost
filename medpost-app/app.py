""" Medpost Version 0.9 """
import logging
import os
import requests as re
from datetime import datetime, timedelta
from flask import Flask, render_template, url_for, request, redirect, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user,
                         login_required, logout_user, current_user
                        )
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy.exc import SQLAlchemyError
from bs4 import BeautifulSoup as bs

app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/')

# https reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

#load_dotenv(dotenv_path='.env.dev')
db_path = os.getenv('DATABASE_PATH')
log_path = os.getenv('LOG_PATH')
app.config['SECRET_KEY'] = os.getenv('APP_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Veuillez vous connecter SVP"
login_manager.login_message_category = "error"


logging.basicConfig(filename=log_path,
                    encoding='utf-8',
                    level=logging.DEBUG,
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
    online = db.Column(db.Integer, nullable=False)
    newspaper = db.Column(db.Text, nullable=False)

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
    is_admin = db.Column(db.Boolean, nullable=False)

    def __repr__(self):
        return f"User {self.username} - {self.is_admin}"

########### FIN DATABASE ##############

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_datetime_utils():
    def now_datetime():
        return datetime.now().isoformat(timespec='minutes')
    return {'current_datetime': now_datetime}

def fetch_articles(selectedfeed, newspaper):
    if selectedfeed == 'tous':
        articles = (db.session.query(Articles_rss)
                    .outerjoin(Posts, Articles_rss.id==Posts.id_article)
                    .filter(Posts.id_article.is_(None))
                    .filter(Articles_rss.online==1)
                    .filter(Articles_rss.newspaper==newspaper)
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
        subquery = (db.session.query(Posts.id_article) # Articles postés sur selectedfeed
                     .join(Networks, Posts.network == Networks.id)
                     .filter(Networks.name == selectedfeed)
                     .distinct()
                     .subquery())

        articles = (db.session.query(Articles_rss)
                    .filter(~Articles_rss.id.in_(db.select(subquery))) # articles postés
                    .filter(Articles_rss.online == 1)
                    .filter(Articles_rss.newspaper == newspaper)
                    .with_entities(Articles_rss.id,
                                    Articles_rss.title,
                                    Articles_rss.summary,
                                    Articles_rss.link,
                                    Articles_rss.image_url,
                                    Articles_rss.pubdate,
                                   )
                    .distinct()
                    .order_by(Articles_rss.pubdate.desc())
                    )
    return articles

def fetch_pub_posts(selectedfeed, newspaper):
    if selectedfeed == 'tous':
        articles = (db.session.query(Posts)
                    .outerjoin(Articles_rss, Posts.id_article==Articles_rss.id)
                    .outerjoin(Networks, Posts.network==Networks.id)
                    .filter(Posts.status == 'pub')
                    .filter(Articles_rss.newspaper == newspaper)
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
                    .limit(7)
                    )
    else:
        articles = (db.session.query(Posts)
            .outerjoin(Articles_rss, Posts.id_article==Articles_rss.id)
            .outerjoin(Networks, Posts.network==Networks.id)
            .filter(Networks.name==selectedfeed)
            .filter(Articles_rss.newspaper == newspaper)
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
            .limit(7)
                            )
    return articles

def fetch_planned_posts(selectedfeed, newspaper):
    base_query = (db.session.query(Posts)
                .outerjoin(Articles_rss, Posts.id_article == Articles_rss.id)
                .outerjoin(Networks, Posts.network == Networks.id)
                .filter(Articles_rss.newspaper == newspaper)
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

    if selectedfeed == 'tous':
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
               .filter(Networks.name==network_txt).first()) # récupération de l'id du network
        title = title.rstrip()
        if network_txt == 'X':
            if (title[-1] not in ['.', '!', '?']):
                title += '.'
        elif network_txt == 'Bluesky':
            tagline = tagline.rstrip()
            if (tagline[-1] not in ['.', '!', '?']):
                tagline += '. '
        post = Posts(
            title=title,
            description=description,
            tagline=tagline,
            image_url=image_url,
            date_pub=date_pub,
            status='plan',
            id_article=article_id,
            network=network.id
            )
        db.session.add(post)
        db.session.commit()
        logging.info("Nouveau post sur %s : %s", network_txt, post.title)

def update_post(post_id, title, description, tagline, post_datetime, network):
    date_plan = datetime.strptime(post_datetime, '%Y-%m-%dT%H:%M')
    post_to_modify = db.session.execute(db.select(Posts).filter_by(id=post_id)).scalar_one()
    post_to_modify.title = title
    post_to_modify.description = description
    post_to_modify.tagline = tagline
    post_to_modify.date_pub = date_plan
    post_to_modify.network = db.session.query(Networks.id).filter(Networks.name==network).scalar()
    db.session.commit()
    logging.info("Post mis à jour sur %s: %s", network, title)

def article_to_dict(fetched_article, newspaper):
    article = {}
    article['title'] = fetched_article.title
    article['image_url'] = fetched_article.image_url
    article['summary'] = fetched_article.summary
    article['link'] = fetched_article.link
    article['pubdate'] = fetched_article.pubdate.strftime('%Y-%m-%dT%H:%M')
    article['newspaper'] = newspaper
    article['id'] = fetched_article.id
    logging.debug("Article dict : %s", article)
    return article

def create_article(article_data):
    article = Articles_rss(
        title=article_data['title'],
        link=article_data['link'],
        summary=article_data['summary'],
        image_url=article_data['image_url'],
        pubdate=article_data['pubdate'],
        online=1,
        newspaper=article_data['newspaper']
    )
    try:
        db.session.add(article)
        db.session.commit()
        return article.id
    except Exception as e:
        db.session.rollback()
        logging.warning("Impossible d'enregistrer dans la db l'article %s : %s", article.title, e)
        return None

def fetch_article_http(url):
    response = {}
    try:
        http_response = re.get(url, timeout=10)
        soup = bs(http_response.text, 'html.parser')
        response['title'] = soup.find('meta', attrs = {"name":"twitter:title"}).attrs['content']
        response['image_url'] = soup.find('meta', attrs = {"name":"twitter:image"}).attrs['content']
        response['summary'] = soup.find('meta', attrs = {"name":"twitter:description"}).attrs['content']
        response['link'] = soup.find('meta', attrs = {"name":"twitter:url"}).attrs['content']
        response['pubdate'] = datetime.now().replace(second=0, microsecond=0)
        return response
    except re.exceptions.RequestException as e:
        logging.error("Échec lors de la lecture URL %s : %s", url, e)
        response['message'] = f"Erreur d'URL {url}"
        return response

def fetch_article_if_exists(url, newspaper):
    article = (db.session.query(Articles_rss)
            .filter(Articles_rss.newspaper == newspaper)
            .where(Articles_rss.link == url)
            .filter(Articles_rss.online==1)
            .first()
    )
    return article

@app.route('/')
@app.route('/index')
@login_required
def home():
    perpage=7
    page = request.args.get('page', 1, type=int)
    selectedfeed = request.args.get('selectedfeed', 'tous', type=str)
    newspaper = request.args.get('newspaper', 'qdm', type=str)
    articles = fetch_articles(selectedfeed, newspaper)
    articles = articles.paginate(per_page=perpage, page=page)
    posts_pub = fetch_pub_posts(selectedfeed, newspaper)
    posts_planned = fetch_planned_posts(selectedfeed, newspaper)
    return render_template('index.html',
                            articles=articles,
                            posts_pub=posts_pub,
                            posts_planned=posts_planned,
                            selectedfeed=selectedfeed,
                            newspaper=newspaper
                            )

@app.route('/delete_article/<int:article_id>/<string:selectedfeed>/<string:newspaper>')
@login_required
def delete_article(article_id, selectedfeed, newspaper):
    article = db.session.get(Articles_rss, article_id)
    article.online = 0
    try:
        db.session.commit()
        logging.info("Suppression de l'article %s - %s", article.id, article.title)
    except SQLAlchemyError as err:
        logging.error("Erreur lors de la suppression de %s : %s", article.title, err)
        db.session.rollback()
    except AttributeError as err:
        logging.error("Erreur inattendue lors de la suppression de l'article : %s", err)
    return redirect(url_for('home', selectedfeed=selectedfeed, newspaper=newspaper))

@app.route('/new_post', methods=['POST'])
@login_required
def new_post():
    article_id = request.form.get('article_id', type=int)
    image_url = request.form.get('image_url', type=str)
    selectedfeed = request.args.get('selectedfeed', type=str)
    newspaper = request.args.get('newspaper', type=str)
    title = request.form.get('title')
    description = request.form.get('description')
    tagline = request.form.get('tagline')
    link = request.form.get('link')
    post_datetime = request.form.get('datetime')
    networks = request.form.getlist('network')
    if networks:
        record_new_post(article_id, image_url, title, description, tagline, post_datetime, networks)
    else:
        logging.info('Aucun post créé')
    return redirect(url_for('home', selectedfeed=selectedfeed, newspaper=newspaper))

@app.route('/edit_post', methods=['POST'])
@login_required
def edit_post():
    post_id = request.form.get('post_id', type=int)
    selectedfeed = request.args.get('selectedfeed', type=str)
    newspaper = request.args.get('newspaper', type=str)
    title = request.form.get('post_title')
    description = request.form.get('post_description')
    tagline = request.form.get('post_tagline')
    link = request.form.get('post_link')
    post_datetime = request.form.get('post_datetime')
    network = request.form.get('post_network')
    update_post(post_id, title, description, tagline, post_datetime, network)
    return redirect(url_for('home', selectedfeed=selectedfeed, newspaper=newspaper))

@app.route('/delete_post')
@login_required
def delete_post():
    post_id = request.args.get('post_id', type=int)
    selectedfeed = request.args.get('selectedfeed', type=str)
    newspaper = request.args.get('newspaper', type=str)
    post = db.session.get(Posts, post_id)
    db.session.delete(post)
    db.session.commit()
    logging.info("Post supprimé : %s", post.title)
    return redirect(url_for('home', selectedfeed=selectedfeed, newspaper=newspaper))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
#            session.permanent = True
            logging.info("Connexion de %s (admin %s)", username, user.is_admin)
            flash(f"Connexion de {username} {'(admin)' if user.is_admin else '(utilisateur)'}")
            return redirect(url_for('home'))
        else:
            flash('Erreur de saisie', 'error')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logging.info("Déconnexion de %s", current_user.username)
    flash(f"Déconnexion de {current_user.username}")
    logout_user()
    return redirect(url_for('login'))

@app.route('/update_tag/<int:network_id>', methods=['POST'])
@login_required
def update_tag(network_id):
    new_tag = request.form.get('new_tag')
    network = db.session.get(Networks, network_id)
    if network:
        network.tag = new_tag
        db.session.commit()
    return redirect(url_for('tags_list'))

@app.route('/tags')
@login_required
def tags_list():
    networks = (db.session
                .query(Networks)
                .with_entities(Networks.id,
                               Networks.name,
                               Networks.tag,
                               )
                .all()
                )
    return render_template('tags_list.html', networks=networks)

@app.route('/import', methods=['POST'])
@login_required
def import_link():
    data = request.get_json()
    link = data.get('importedLink')
    newspaper = data.get('newspaper')  # Récupérer le paramètre newspaper
    logging.info("Lien importé : %s pour le journal %s - Data %s", link, newspaper, data)
    if link:
        fetched_article = fetch_article_if_exists(link, newspaper)    
        if fetched_article is None: # Création del'article si absent de la base
            article_info = fetch_article_http(link)
            article_info['newspaper'] = newspaper
            article_info['id'] = create_article(article_info)
            article_info['pubdate'] =  article_info['pubdate'].strftime('%Y-%m-%dT%H:%M')
            return jsonify(article_info), 200
        else:
            logging.debug("Import - Article existant %s : ", fetched_article)
            article_json = jsonify(article_to_dict(fetched_article, newspaper))
            logging.debug("Article json : %s", article_json.get_data(as_text=True))
            return article_json, 200
    return jsonify({"message": "problème lors de la création de l'article"}), 400

@app.route('/update_user/<int:user_id>', methods=['POST'])
@login_required
def update_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    user = db.session.get(User, user_id)
    if user:
        user.username = request.form.get('username')
        password = request.form.get('password')
        if password:
            user.password = generate_password_hash(password)
        user.is_admin = request.form.get('is_admin') == 'true'
        db.session.commit()
        logging.info("Utilisateur mis à jour : %s", user.username)
        flash(f"Mise à jour de {user.username}")
    return redirect(url_for('admin'))

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    users = db.session.query(User).all()
    return render_template('admin.html', users=users)

if __name__ == '__main__':
    #app.run(port=8000, debug=True)
    app.run(port=8000)
