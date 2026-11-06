from flask import Flask, render_template, request, redirect
from flask_login import login_required, current_user
from flask_wtf import CSRFProtect
from opentelemetry import trace
from werkzeug.middleware.proxy_fix import ProxyFix

from .tracing import init_app as init_tracing
from .models import init_app as init_db, db
from .login import init_app as init_login
from .login.pebble import ensure_pebble
from .oauth import init_app as init_oauth
from .api import init_app as init_api
from .redis import init_app as init_redis
from .billing import init_app as init_billing
from .wizard import init_app as init_wizard
from .discourse import init_app as init_discourse
from .voting import init_app as init_voting

from .settings import config

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
init_tracing(app)
CSRFProtect(app)
app.config.update(**config)
# Before ProxyFix we never saw requests as HTTPS, so Flask-WTF's HTTPS-only
# Referer check never ran.  Keep it that way rather than start rejecting
# browsers that strip Referer; the CSRF token is still required.
app.config['WTF_CSRF_SSL_STRICT'] = False

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


@app.before_request
def before_request():
    span = trace.get_current_span()
    if request.endpoint:
        span.set_attribute("flask.endpoint", request.endpoint)
    if current_user.is_authenticated:
        span.set_attribute("user.id", current_user.id)

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
