import secrets
from flask import Blueprint, render_template, session, request, redirect, abort, url_for, current_app
from flask_login import LoginManager, login_user, current_user, login_required
from flask_oauthlib.client import OAuth

from ..models import db, User, UserIdentity

login_manager = LoginManager()
login_blueprint = Blueprint('login', __name__)
auth = OAuth()

secure_url_for = lambda x: url_for(x, _external=True, _scheme='https' if not current_app.debug else 'http')


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id=int(user_id)).first()


@login_blueprint.route("/")
def login():
    session['next'] = request.args.get('next', None)
    return render_template('login.html')


@login_blueprint.route("/demand_pebble")
@login_required
def demand_pebble():
    return render_template('pebble.html')


def redirect_next():
    next_url = session.get('next', '/')
    if next_url.startswith('//') or ':' in next_url:
        next_url = '/'
    return redirect(next_url)


def prepare_state():
    session['oauth_state'] = secrets.token_urlsafe()


def get_state():
    return session['oauth_state']


def validate_state():
    expected_state = session['oauth_state']
    if expected_state is None:
        abort(401)
    del session['oauth_state']
    if request.args.get('state') != expected_state:
        abort(401)


def complete_auth_flow(idp_name, idp_user_id, user_name, user_email):
    user = current_user._get_current_object()
    identity = UserIdentity.query.filter_by(idp=idp_name, idp_user_id=idp_user_id).one_or_none()
    if not user.is_authenticated:
        if identity is not None:
            user = identity.user
        else:
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
    db.session.commit()
    login_user(identity.user, remember=True)
    return redirect_next()


def init_app(app):
    app.register_blueprint(login_blueprint, url_prefix='/auth')
    login_manager.login_view = 'login.login'
    login_manager.init_app(app)
    auth.init_app(app)
