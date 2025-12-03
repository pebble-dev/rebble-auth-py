import secrets
from flask import Blueprint, render_template, session, request, redirect, abort, url_for, current_app, Response
from flask_login import LoginManager, login_user, current_user, login_required, logout_user
from flask_oauthlib.client import OAuth
from ..settings import config

from ..models import db, User, UserIdentity

login_manager = LoginManager()
login_blueprint = Blueprint('login', __name__)
auth = OAuth()

secure_url_for = lambda x: url_for(x, _external=True, _scheme='https' if not current_app.debug else 'http')
dummy_enabled = False


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id=int(user_id)).first()


@login_blueprint.route("/")
def login():
    session['next'] = request.args.get('next', None)
    return render_template('login.html', enable_dummy=dummy_enabled)


@login_blueprint.route("/demand_pebble")
@login_required
def demand_pebble():
    return render_template('pebble.html')

@login_blueprint.route("/logout")
def logout():
    logout_user()
    request_source = request.args.get('from') if request.args.get('from') is not None else "auth"
    return_url = "/"
    try:
        return_url = config[f'RETURN_{request_source.upper()}']
    except KeyError:
        pass
    return render_template('logged-out.html', return_url=return_url)

def redirect_next():
    next_url = session.get('next') or '/'
    if next_url.startswith('//') or ':' in next_url:
        next_url = '/'
    return redirect(next_url)


def prepare_state():
    session['oauth_state'] = secrets.token_urlsafe()


def get_state():
    return session['oauth_state']


def validate_state():
    if 'oauth_state' not in session:
        abort(Response(render_template('login-timed-out.html'), 401))
    expected_state = session['oauth_state']
    if expected_state is None:
        abort(Response(render_template('login-timed-out.html'), 401))
    del session['oauth_state']
    if request.args.get('state') != expected_state:
        abort(Response(render_template('login-timed-out.html'), 401))


def complete_auth_flow(idp_name, idp_user_id, user_name, user_email):
    user = current_user._get_current_object()
    identity = UserIdentity.query.filter_by(idp=idp_name, idp_user_id=idp_user_id).one_or_none()
    if not user.is_authenticated:
        if identity is not None:
            user = identity.user
        else:
            if idp_name == 'twitter':
                return render_template('twitter-not-available.html'), 401
            if user_email is None or user_email == '':
                return render_template('email-required.html'), 401
            user = User(name=user_name, email=user_email)
            db.session.add(user)
            identity = UserIdentity(user=user, idp=idp_name, idp_user_id=idp_user_id)
            db.session.add(identity)
            print("Creating new user...")
    else:
        if not identity:
            print('New identity for logged in user')
            identity = UserIdentity(user=user, idp=idp_name, idp_user_id=idp_user_id)
            db.session.add(identity)
        else:
            print('Known identity')
            if user != identity.user:
                return render_template('already-associated.html')
    db.session.commit()
    login_user(identity.user, remember=True)
    return redirect_next()


def init_app(app):
    global dummy_enabled
    if app.env == 'development':
        dummy_enabled = True
    app.register_blueprint(login_blueprint, url_prefix='/auth')
    login_manager.login_view = 'login.login'
    login_manager.init_app(app)
    auth.init_app(app)
    app.extensions['csrf'].exempt(login_blueprint)
