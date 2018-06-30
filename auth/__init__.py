from flask import Flask, render_template
from flask_login import login_required, current_user
from flask_sslify import SSLify
from flask_wtf import CSRFProtect

from .models import init_app as init_db, db
from .login import init_app as init_login
from .login.pebble import ensure_pebble, pebble
from .oauth import init_app as init_oauth
from .api import init_app as init_api
from .redis import init_app as init_redis
from .billing import init_app as init_billing

from .settings import config

app = Flask(__name__)
CSRFProtect(app)
app.config.update(**config)
sslify = SSLify(app)
if not app.debug:
    app.config['PREFERRED_URL_SCHEME'] = 'https'
init_db(app)
init_redis(app)
init_login(app)
init_oauth(app)
init_billing(app)
init_api(app)


@app.route("/")
@login_required
@ensure_pebble
def root():
    user_info = pebble.request('me.json').data
    return render_template('logged-in.html', pebble_auth_uid=current_user.pebble_auth_uid,
                           name=current_user.name, email=current_user.email, pebble_email=user_info['email'])


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
