from flask import Flask, render_template
from flask_login import login_required
from flask_sslify import SSLify

from .models import init_app as init_db
from .login import init_app as init_login
from .login.pebble import ensure_pebble
from .oauth import init_app as init_oauth
from .api import init_app as init_api

from .settings import config


app = Flask(__name__)
app.config.update(**config)
sslify = SSLify(app)
if not app.debug:
    app.config['PREFERRED_URL_SCHEME'] = 'https'
init_db(app)
init_login(app)
init_oauth(app)
init_api(app)


@app.route("/")
@login_required
@ensure_pebble
def root():
    return render_template('logged-in.html')

@app.route("/tos")
def tos():
    return render_template('terms.html')

@app.route("/privacy")
def privacy():
    return render_template('privacy.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
