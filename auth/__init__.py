from flask import Flask, render_template, request
from flask_login import login_required, current_user
from flask_sslify import SSLify
from flask_wtf import CSRFProtect

import beeline
from beeline.middleware.flask import HoneyMiddleware

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
if config['HONEYCOMB_KEY']:
     beeline.init(writekey=config['HONEYCOMB_KEY'], dataset='rws', service_name='auth')
     HoneyMiddleware(app, db_events = True)
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


# XXX: upstream this
import beeline

@app.before_request
def before_request():
    beeline.add_context_field("route", request.endpoint)
    if current_user.is_authenticated:
        beeline.add_context_field("user", current_user.id)

@app.route("/")
@login_required
def root():
    return render_template('logged-in.html', name=current_user.name, email=current_user.email)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# XXX: upstream this
from wrapt import wrap_function_wrapper
import jinja2
def _render_template(fn, instance, args, kwargs):
    span = beeline.start_span(context = {
        "name": "jinja2_render_template",
        "template.name": instance.name or "[string]",
    })
    
    try:
        return fn(*args, **kwargs)
    finally:
        beeline.finish_span(span)

wrap_function_wrapper('jinja2', 'Template.render', _render_template)
