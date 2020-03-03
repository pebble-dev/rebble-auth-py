from .settings import config

# Lightstep tracing
from ddtrace import tracer, patch_all
from ddtrace.propagation.b3 import B3HTTPPropagator
if config['LIGHTSTEP_KEY'] is not None:
    tracer.set_tags({'lightstep.service_name': 'auth', 'lightstep.access_token': config['LIGHTSTEP_KEY']})
    tracer.configure(http_propagator=B3HTTPPropagator)
    print("yes, lightstep is on!")
    patch_all()

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
from .wizard import init_app as init_wizard

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
init_wizard(app)


@app.route("/")
@login_required
def root():
    return render_template('logged-in.html', name=current_user.name, email=current_user.email)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
