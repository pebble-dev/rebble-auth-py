from flask import Flask, render_template, g
from flask_login import login_required, current_user
from flask_sslify import SSLify

from .models import init_app as init_db
from .login import init_app as init_login
from .login.pebble import ensure_pebble, pebble
from .oauth import init_app as init_oauth
from .api import init_app as init_api
from .redis import init_app as init_redis

from .settings import config


app = Flask(__name__)
app.config.update(**config)
sslify = SSLify(app)
if not app.debug:
    app.config['PREFERRED_URL_SCHEME'] = 'https'
init_db(app)
init_redis(app)
init_login(app)
init_oauth(app)
init_api(app)


@app.route("/")
@login_required
def root():
    if current_user.pebble_token:
        pebble_email = pebble.request('me.json').data['email']
    else:
        pebble_email = None
    has_data = pebble_email is not None and current_user.id <= 34559
    return render_template('logged-in.html', name=current_user.name, email=current_user.email,
                           pebble_email=pebble_email, has_data=has_data)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
