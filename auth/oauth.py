import collections
from datetime import datetime, timedelta

from flask import Blueprint, abort
from flask_oauthlib.provider import OAuth2Provider
from oauthlib.common import generate_token as generate_random_token
from flask_login import current_user, login_required

from .models import db, IssuedToken, AuthClient, User

oauth_bp = Blueprint('oauth_bp', __name__)
oauth = OAuth2Provider()

Grant = collections.namedtuple('Grant', 'client_id code user scopes expires redirect_uri')
def delete_grant(self: Grant):
    del grants[self.client_id, self.code]
Grant.delete = delete_grant
grants = {}


@oauth.grantgetter
def load_grant(client_id, code):
    return grants[client_id, code]


@oauth.grantsetter
def set_grant(client_id, code, request, *args, **kwargs):
    if not current_user.is_authenticated:
        return None
    expires = datetime.utcnow() + timedelta(seconds=100)
    grant = Grant(client_id, code['code'], current_user._get_current_object(), request.scopes, expires, request.redirect_uri)
    grants[grant.client_id, grant.code] = grant
    return grant


@oauth.tokengetter
def get_token(access_token=None, refresh_token=None):
    if access_token:
        # There are two valid 'tokens': ones we've issued, and the Pebble token.
        # Because we don't actually store the pebble token as an issued token, we have to
        # check for it here and invent a token if it's the one we tried to use.
        token = IssuedToken.query.filter_by(access_token=access_token).one_or_none()
        if token:
            return token
        user = User.query.filter_by(pebble_token=access_token).one_or_none()
        if user:
            return IssuedToken(access_token=access_token, refresh_token=None, expires=None, client_id=None, user=user,
                               scopes=['pebble', 'pebble_token', 'profile'])
    elif refresh_token:
        return IssuedToken.query.filter_by(refresh_token=refresh_token).one_or_none()


@oauth.tokensetter
def set_token(token, request, *args, **kwargs):
    expires_in = token.get('expires_in')
    expires = datetime.utcnow() + timedelta(seconds=expires_in)
    scopes = token['scope'].split(' ')

    token = IssuedToken(access_token=token['access_token'], refresh_token=token['refresh_token'], expires=expires,
                        client_id=request.client.client_id, user_id=request.user.id,
                        scopes=scopes)

    # We can't store the token if it's a pebble token, because pebble tokens aren't unique, and so do terrible things
    # to the database structure. This regrettably means we're going to have to carry a hack for supporting pebble
    # tokens around forever.
    if 'pebble_token' not in scopes:
        db.session.add(token)
        db.session.commit()
    return token


@oauth.clientgetter
def get_client(client_id):
    return AuthClient.query.filter_by(client_id=client_id).first()


@oauth_bp.route('/authorise', methods=['GET', 'POST'])
@login_required
@oauth.authorize_handler
def authorise(*args, **kwargs):
    return True


@oauth_bp.route('/token', methods=['GET', 'POST'])
@oauth.token_handler
def access_token():
    return None


def generate_token(request, refresh_token=False):
    # We take the 'pebble_token' scope to mean that we're authenticating a pebble service that expects to get
    # a pebble token, which means we shouldn't generate a new one for it.
    if 'pebble_token' in request.scopes and not refresh_token:
        if request.user.pebble_token:
            return request.user.pebble_token
        else:
            abort(401)
    return generate_random_token()


def init_app(app):
    app.config['OAUTH2_PROVIDER_TOKEN_EXPIRES_IN'] = 315576000  # 10 years
    app.config['OAUTH2_PROVIDER_TOKEN_GENERATOR'] = generate_token
    oauth.init_app(app)
    app.register_blueprint(oauth_bp, url_prefix='/oauth')
