from flask import Flask, render_template, request, redirect
from flask_login import login_required, current_user
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

import os

import beeline
from beeline.middleware.flask import HoneyMiddleware
import beeline.propagation.w3c as w3c

from .models import init_app as init_db, db
from .login import init_app as init_login
from .login.pebble import ensure_pebble, pebble
from .oauth import init_app as init_oauth
from .api import init_app as init_api
from .redis import init_app as init_redis
from .billing import init_app as init_billing
from .wizard import init_app as init_wizard
from .discourse import init_app as init_discourse
from .voting import init_app as init_voting

from .settings import config

from wrapt import wrap_function_wrapper

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
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
CSRFProtect(app)
app.config.update(**config)
# Before ProxyFix we never saw requests as HTTPS, so Flask-WTF's HTTPS-only
# Referer check never ran.  Keep it that way rather than start rejecting
# browsers that strip Referer; the CSRF token is still required.
app.config['WTF_CSRF_SSL_STRICT'] = False
if os.environ.get('O11Y_SHOULD_USE_W3C_TRACE_HEADERS', False):
    # Only turn this on once EVERYTHING has migrated to the new
    # rws_common version that supports W3C trace headers.
    beeline.init(writekey=config['HONEYCOMB_KEY'], dataset='rws', service_name='auth', sampler_hook=sampler, http_trace_propagation_hook=w3c.http_trace_propagation_hook)
else:
    beeline.init(writekey=config['HONEYCOMB_KEY'], dataset='rws', service_name='auth', sampler_hook=sampler)
HoneyMiddleware(app, db_events = True)

# Replaces Flask-SSLify.  Internal kube requests come in as 'auth:8080';
# it's impossible for the outside world to call us by that name,
# since that won't make it past the GCLB.
@app.before_request
def redirect_to_https():
    if request.is_secure or app.debug or request.host == 'auth:8080' or request.path.startswith('/heartbeat'):
        return
    return redirect(request.url.replace('http://', 'https://', 1))

if not app.debug:
    app.config['PREFERRED_URL_SCHEME'] = 'https'
init_db(app)
init_redis(app)
init_login(app)
init_oauth(app)
init_billing(app)
init_api(app)
init_wizard(app)
init_discourse(app)
init_voting(app)


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
