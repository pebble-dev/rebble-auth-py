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

# Avoid redirecting internal kube requests.  Note that this needs to happen
# before the SSLify is created.  Note that I don't think it's possible for
# the outside world to try to call us by 'auth:8080', since that won't make
# it past the GCLB.
#
# XXX: Package this up in a 'just Rebble things' package, along with some of
# our other Beeline hacks.

from wrapt import wrap_function_wrapper

def _redirect_to_ssl(fn, instance, args, kwargs):
    if request.host == 'auth:8080':
        return
    return fn(*args, **kwargs)

wrap_function_wrapper('flask_sslify', 'SSLify.redirect_to_ssl', _redirect_to_ssl)

from beeline.trace import _should_sample
def sampler(fields):
    sample_rate = 2

    route = fields.get('route') or ''
    if route == 'heartbeat':
        sample_rate = 100
    elif route == 'api.me':
        sample_rate = 10
    elif 'billing.' in route:
        sample_rate = 1

    response_code = fields.get('response.status_code')
    if response_code != 200:
        sample_rate = 1
    
    if _should_sample(fields.get('trace.trace_id'), sample_rate):
        return True, sample_rate
    return False, 0

app = Flask(__name__)
CSRFProtect(app)
app.config.update(**config)
beeline.init(writekey=config['HONEYCOMB_KEY'], dataset='rws', service_name='auth', sampler_hook=sampler)
HoneyMiddleware(app, db_events = True)
sslify = SSLify(app, skips=['heartbeat'])
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


@app.route("/heartbeat")
@app.route("/auth/heartbeat")
def heartbeat():
    return "ok"

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# XXX: upstream this
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
