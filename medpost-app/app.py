""" Medpost Version 0.9 """
import logging
import os
import requests
import requests as re
import io

from datetime import datetime, timedelta
from flask import Flask, render_template, url_for, request, redirect, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user,
                         login_required, logout_user, current_user
                        )
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy.exc import SQLAlchemyError
from bs4 import BeautifulSoup as bs
from PIL import Image

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
    nid = db.Column(db.Integer, nullable=False, index=True)
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
                    .filter(Articles_rss.nid != 0)
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
                    .filter(Articles_rss.nid != 0)
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
    return articles, articles.count()

def clean_and_resize_image(image_bytes, max_size=500000):
    """
    Supprime les métadonnées et réduit la taille de l'image si nécessaire.
    Retourne les bytes de l'image nettoyée, ou None si impossible.
    """
    img = Image.open(io.BytesIO(image_bytes))
    # Convertir en RGB pour éviter les problèmes de mode
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    quality = 95
    while True:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= max_size or quality < 30:
            break
        quality -= 5  # Réduire la qualité pour compresser
    if len(data) > max_size:
        # Dernier recours : redimensionner l'image
        width, height = img.size
        while len(data) > max_size and width > 100 and height > 100:
            width = int(width * 0.9)
            height = int(height * 0.9)
            img = img.resize((width, height), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            data = buffer.getvalue()
    if len(data) > max_size:
        return None  # Impossible de réduire suffisamment
    return data

def save_image(image_file):
    logging.debug("Sauvegarde de image_file : %s", image_file.filename)
    save_path = "static/images/"
    filename = secure_filename(image_file.filename) 
    image_bytes = image_file.read()
    cleaned_bytes = clean_and_resize_image(image_bytes)
    if cleaned_bytes is None:
        logging.warning("Impossible de réduire l'image %s", filename)
        return "images/no_picture.jpg"
    with open(os.path.join(save_path, filename), "wb") as f:
        f.write(cleaned_bytes)
    # Remettre le pointeur du fichier à zéro pour d'autres utilisations éventuelles
    # image_file.seek(0)
    return "images/" + filename

def record_new_post(form_data, image_file):
    # form_data  ={
    #  'article_id': '1069',
    #  'network': 'Bluesky',
    #  'image_url': 'https://',
    #  'description': 'Les Drs Estelle Touboul et Maxime',
    #  'title': 'Pour créer le logiciel'
    #  'tagline': 'Pour créer le ', 
    #  'datetime': '2025-05-06T10:18'}
    date_pub = datetime.strptime(form_data['datetime'], '%Y-%m-%dT%H:%M')
    network = form_data['network']
    network_id = (db.session.query(Networks.id)
                  .filter(Networks.name==network)
                  .first())[0]
    article_id = form_data['article_id']
    description = form_data['description']
    if image_file:
        image_url = save_image(image_file)
    else:
            image_url = form_data['image_url']
    title = form_data['title'].rstrip()
    if network == 'X':
        tagline = None # Pas de tagline fourni par le fomulaire X
        if (title[-1] not in ['.', '!', '?']):
            title += '.'
    else:
        tagline = form_data['tagline']
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
        network=network_id
        )
    db.session.add(post)
    db.session.commit()
    logging.info("Nouveau post sur %s : %s", network, title)

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

def article_to_dict(imported_article, newspaper):
    article = {}
    article['title'] = imported_article.title
    article['image_url'] = imported_article.image_url
    article['summary'] = imported_article.summary
    article['link'] = imported_article.link
    article['pubdate'] = imported_article.pubdate.strftime('%Y-%m-%dT%H:%M')
    article['newspaper'] = newspaper
    article['id'] = imported_article.id
    logging.debug("Article dict : %s", article)
    return article

def create_article(article_data):
    article = Articles_rss(
        nid=article_data['nid'],
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

def extract_data_from_html(html_article, url):
    article_data = {}
    try:
        article_data['title'] = html_article.find('meta', attrs = {"name":"twitter:title"}).attrs['content']
        try:
            article_data['image_url'] = html_article.find('meta', attrs = {"name":"twitter:image"}).attrs['content']
        except Exception: # Pas de vignette dans la Twitter card du site
            article_data['image_url'] = "images/no_picture.jpg"
#        article_data['summary'] = html_article.find('meta', attrs = {"name":"twitter:description"}).attrs['content']
        description = html_article.find('meta', attrs={"name": "twitter:description"})
        article_data['summary'] = description.get('content', "") if description else ""
        article_data['link'] = html_article.find('meta', attrs = {"name":"twitter:url"}).attrs['content']
        #article_data['pubdate'] = datetime.now().replace(second=0, microsecond=0)
        return article_data
    except re.exceptions.RequestException as e:
        logging.error("Échec lors de la lecture URL %s : %s", url, e)
        article_data['message'] = f"Erreur d'URL {url}"
        return article_data

def fetch_article_html(url: str):
    try:
        http_article_data = requests.get(url, timeout=10)
        html_article = bs(http_article_data.text, 'html.parser')
        return html_article
    except requests.exceptions.RequestException as e:
        logging.error("Échec lors de la lecture URL %s : %s", url, e)
        return None

def get_article_nid(html_article):
        # <article data-history-node-id="248526"
        try:
            nid_article = html_article.article['data-history-node-id']
            logging.debug("NID : %s", nid_article)
            return nid_article
        except Exception:
            logging.error("Pas de NID pour l'article")
            return None

def read_article_if_exists(url, newspaper):
    html_article = fetch_article_html(url)
    nid = get_article_nid(html_article)
    article = (db.session.query(Articles_rss)
               .where(Articles_rss.nid==nid)
               .where(Articles_rss==newspaper)
               .where(Articles_rss.online==1)
               ).first()
    return article, html_article, nid

def update_article(article_data) -> bool:
    logging.debug("Article à updater : %s", article_data)
    article_to_update = db.session.execute(db.select(Articles_rss).filter_by(id=article_data['id'])).scalar_one()
    article_to_update.title = article_data['title']
    article_to_update.image_url = article_data['image_url']
    article_to_update.summary = article_data['summary']
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logging.error("Erreur lors de la mise à jour de l'article %s : %s", article_data['title'], e)
        return False

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
    posts_planned, nb_posts_planned = fetch_planned_posts(selectedfeed, newspaper)
    return render_template('index.html',
                           articles=articles,
                           posts_pub=posts_pub,
                           posts_planned=posts_planned,
                           selectedfeed=selectedfeed,
                           newspaper=newspaper,
                           nb_posts_planned=nb_posts_planned
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
    # selectedfeed = request.args.get('selectedfeed', type=str)
    # newspaper = request.args.get('newspaper', type=str)  
    form_data = dict(request.form)
    selectedfeed = form_data['selectedfeed']
    newspaper = form_data['newspaper']
    logging.debug("Request : %s", request.files)
    if 'imageFile' in request.files:
        image_file = request.files['imageFile']
        logging.debug("réception de imagefile : %s", image_file)
    else:
        image_file = None
    record_new_post(form_data, image_file)
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
    # link = request.form.get('post_link')
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
        imported_article, html_article, nid = read_article_if_exists(link, newspaper)    
        if imported_article is None: # Création de l'article si absent de la base
            article_data = extract_data_from_html(html_article, link)
            article_data['nid'] = nid
            article_data['newspaper'] = newspaper
            article_data['pubdate'] = datetime.now().replace(second=0, microsecond=0)
            article_data['id'] = create_article(article_data)
            article_data['pubdate'] =  article_data['pubdate'].strftime('%Y-%m-%dT%H:%M')
            return jsonify(article_data), 200
        else:
            logging.debug("Import - Article existant %s : ", imported_article)
            article_json = jsonify(article_to_dict(imported_article, newspaper))
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

@app.route('/new_post_image', methods=['POST'])
@login_required
def new_post_image():
    form_data = dict(request.form)
    selectedfeed = form_data['selectedfeed']
    newspaper = form_data['newspaper']
    fake_article = {}
    fake_article['nid'] = 0
    fake_article['title'] = form_data['title']
    fake_article['link'] = ""
    fake_article['summary'] = ""
    fake_article['image_url'] = "images/no_picture.jpg"
    fake_article['pubdate']  = datetime.strptime(form_data['datetime'], '%Y-%m-%dT%H:%M')
    fake_article['online'] = 0
    fake_article['newspaper'] = form_data['newspaper']
    id_article = create_article(fake_article)
    if 'imageFile' in request.files:
        image_file = request.files['imageFile']
        logging.debug("réception de imagefile : %s", image_file)
    else:
        image_file = None
    form_data['article_id'] = id_article   
    record_new_post(form_data, image_file)
    return redirect(url_for('home', selectedfeed=selectedfeed, newspaper=newspaper))

@app.route('/refresh')
@login_required
def refresh():
    link = request.args.get('link', type=str)
    selectedfeed = request.args.get('selectedfeed', type=str)
    newspaper = request.args.get('newspaper', type=str)
    html_article = fetch_article_html(link)
    article_data = extract_data_from_html(html_article, link)
    article_data['id'] = request.args.get('article_id', type=int)
    update_success = update_article(article_data)
    if update_success:
        logging.debug("Refresh de %s réussi", article_data['title'])
        flash(f"Refresh réussi : {article_data['title']}")
    else:
        flash("Erreur lors du refresh")
    return redirect(url_for('home', selectedfeed=selectedfeed, newspaper=newspaper))

if __name__ == '__main__':
    #app.run(port=8000, debug=True)
    app.run(port=8000)
