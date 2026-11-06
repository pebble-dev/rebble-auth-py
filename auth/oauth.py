from datetime import datetime, timedelta
from functools import wraps
from types import SimpleNamespace
import os

from authlib.common.security import generate_token
from authlib.common.urls import add_params_to_uri
from authlib.integrations.flask_oauth2 import AuthorizationServer as _AuthorizationServer, ResourceProtector
from authlib.integrations.flask_oauth2.requests import FlaskOAuth2Request
from authlib.oauth2 import OAuth2Error
from authlib.oauth2.rfc6749 import grants, MissingAuthorizationError
from authlib.oauth2.rfc6749.errors import AccessDeniedError, InvalidScopeError
from authlib.oauth2.rfc6749.util import scope_to_list
from authlib.oauth2.rfc6750 import BearerTokenValidator as _BearerTokenValidator, InsufficientScopeError, InvalidTokenError
from flask import Blueprint, abort, render_template, request, redirect, url_for
from flask_login import current_user, login_required
from flask_cors import cross_origin

from auth.login.base import demand_pebble
from .models import db, IssuedToken, AuthClient, User
from .redis import client as redis
import json

from flask.cli import with_appcontext
import click

TOKEN_EXPIRES_IN = 315576000  # 10 years
TOKEN_LENGTH = 30
TOKEN_ENDPOINT_AUTH_METHODS = ['client_secret_basic', 'client_secret_post', 'none']

oauth_bp = Blueprint('oauth_bp', __name__)


class Grant:
    def __init__(self, client_id, code, user_id, scopes, redirect_uri):
        self.client_id = client_id
        self.code = code
        self.user_id = user_id
        self.scopes = scopes
        self.redirect_uri = redirect_uri

    @property
    def user(self):
        return User.query.filter_by(id=self.user_id).one()

    def delete(self):
        redis.delete(self.key)

    def get_redirect_uri(self):
        return self.redirect_uri

    def get_scope(self):
        return ' '.join(self.scopes)

    @property
    def key(self):
        return self.redis_key(self.client_id, self.code)

    def serialise(self):
        return json.dumps([self.client_id, self.code, self.user_id, self.scopes, self.redirect_uri]).encode('utf-8')

    @classmethod
    def deserialise(cls, serialised):
        return cls(*json.loads(serialised.decode('utf-8')))

    @classmethod
    def redis_key(cls, client_id, code):
        return f'grant-{client_id}-{code}'


def load_grant(client_id, code):
    serialised = redis.get(Grant.redis_key(client_id, code))
    return Grant.deserialise(serialised) if serialised else None


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


def save_token(token, request):
    expires = datetime.utcnow() + timedelta(seconds=token['expires_in'])
    scopes = token.get('scope', '').split(' ')

    token = IssuedToken(access_token=token['access_token'], refresh_token=token['refresh_token'], expires=expires,
                        client_id=request.client.client_id, user_id=request.user.id,
                        scopes=scopes)

    db.session.add(token)
    db.session.commit()
    return token


def get_client(client_id):
    return AuthClient.query.filter_by(client_id=client_id).one_or_none()


def generate_bearer_token(**kwargs):
    return generate_token(TOKEN_LENGTH)


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = TOKEN_ENDPOINT_AUTH_METHODS
    TOKEN_ENDPOINT_HTTP_METHODS = ['GET', 'POST']
    AUTHORIZATION_CODE_LENGTH = TOKEN_LENGTH

    def validate_authorization_request(self):
        redirect_uri = super().validate_authorization_request()
        if not set(scope_to_list(self.request.scope) or []) <= set(self.request.client.default_scopes or []):
            raise InvalidScopeError(redirect_uri=redirect_uri)
        return redirect_uri

    def save_authorization_code(self, code, request):
        grant = Grant(request.client.client_id, code, request.user.id, scope_to_list(request.scope) or [],
                      request.payload.redirect_uri)
        redis.set(grant.key, grant.serialise(), ex=100)

    def query_authorization_code(self, code, client):
        return load_grant(client.client_id, code)

    def delete_authorization_code(self, authorization_code):
        authorization_code.delete()

    def authenticate_user(self, authorization_code):
        return authorization_code.user


class RefreshTokenGrant(grants.RefreshTokenGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = TOKEN_ENDPOINT_AUTH_METHODS
    TOKEN_ENDPOINT_HTTP_METHODS = ['GET', 'POST']
    INCLUDE_NEW_REFRESH_TOKEN = True

    def authenticate_refresh_token(self, refresh_token):
        return get_token(refresh_token=refresh_token)

    def authenticate_user(self, refresh_token):
        return refresh_token.user

    def revoke_old_credential(self, refresh_token):
        pass


class OAuth2Request(FlaskOAuth2Request):
    # Accept token-endpoint parameters from the query string too, as oauthlib did.
    @property
    def form(self):
        return self._request.values


class AuthorizationServer(_AuthorizationServer):
    def create_oauth2_request(self, _request):
        return OAuth2Request(request)


class BearerTokenValidator(_BearerTokenValidator):
    def authenticate_token(self, token_string):
        return get_token(access_token=token_string)

    def validate_token(self, token, scopes, request):
        if not token or (token.expires is not None and datetime.utcnow() > token.expires):
            raise InvalidTokenError()
        if scopes and not set(token.scopes or []) & set(scopes):
            raise InsufficientScopeError()


class OAuth(ResourceProtector):
    def parse_request_authorization(self, _request):
        auth = request.headers.get('Authorization')
        token = auth[7:] if auth is not None else request.values.get('access_token')
        if not token:
            raise MissingAuthorizationError(self._default_auth_type, self._default_realm)
        return self.get_token_validator('bearer'), token

    def require_oauth(self, *scopes):
        def wrapper(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                try:
                    token = self.acquire_token(scopes)
                except OAuth2Error:
                    abort(401)
                request.oauth = SimpleNamespace(user=token.user, scopes=list(scopes), access_token=token,
                                                client=token.client)
                return f(*args, **kwargs)
            return decorated
        return wrapper


authorization = AuthorizationServer(query_client=get_client, save_token=save_token)
oauth = OAuth()
oauth.register_token_validator(BearerTokenValidator())


def redirect_with_error(error):
    if error.redirect_uri and request.values.get('redirect_uri'):
        return redirect(add_params_to_uri(error.redirect_uri, error.get_body()))
    return redirect(add_params_to_uri(url_for('oauth_bp.oauth_error'), error.get_body()))


@oauth_bp.route('/authorise', methods=['GET', 'POST'])
@login_required
def authorise():
    try:
        grant = authorization.get_consent_grant(end_user=current_user._get_current_object())
    except OAuth2Error as e:
        return redirect_with_error(e)
    client = grant.request.client

    if request.method == 'POST':
        if 'confirm' not in request.form:
            return redirect_with_error(AccessDeniedError(state=request.values.get('state'), redirect_uri=grant.redirect_uri))
    elif not (request.method == 'GET' and client.is_rws):
        return render_template('oauthorise.html', client=client)

    return authorization.create_authorization_response(grant=grant, grant_user=current_user._get_current_object())

@oauth_bp.route('/token', methods=['GET', 'POST'])
@cross_origin()
def access_token():
    return authorization.create_token_response()


@oauth_bp.route('/error')
def oauth_error():
    return render_template('oauth-error.html',
                           error=request.args.get('error', 'unknown'),
                           error_description=request.args.get('error_description', '')), 400


@click.command('create_oauth_client')
@with_appcontext
@click.argument('name')
@click.option('--redirect_uri', multiple=True, required=True)
@click.option('--is_rws', is_flag=True)
@click.option('--confidential', is_flag=True)
@click.option('--scope', multiple=True)
def create_client(name, redirect_uri, confidential, scope, is_rws):
    client_id = generate_token(24)
    client_secret = 'secret_%s' % generate_token(32)

    print("Creating token for \"%s\":" % name)
    print("    Consumer key: %s" % client_id)
    print("    Consumer secret: %s" % client_secret)

    client = AuthClient(
        name = name,
        client_id = client_id,
        client_secret = client_secret,
        redirect_uris = redirect_uri,
        is_confidential = confidential,
        default_scopes = scope,
        is_rws = is_rws
        )

    db.session.add(client)
    db.session.commit()

def init_app(app):
    # XXX: so this is a bit of a weird situation. Auhtlib doesn't like insecure transport (rightfully so),
    # but enabling insecure transport would break internal kube requests.
    # as far as I'm aware, there isn't a way to tell Authlib "hey, required secure trasnport from here, but not here"
    os.environ.setdefault('AUTHLIB_INSECURE_TRANSPORT', '1')
    app.config['OAUTH2_TOKEN_EXPIRES_IN'] = {'authorization_code': TOKEN_EXPIRES_IN, 'refresh_token': TOKEN_EXPIRES_IN}
    app.config['OAUTH2_ACCESS_TOKEN_GENERATOR'] = generate_bearer_token
    app.config['OAUTH2_REFRESH_TOKEN_GENERATOR'] = generate_bearer_token
    authorization.init_app(app)
    authorization.register_grant(AuthorizationCodeGrant)
    authorization.register_grant(RefreshTokenGrant)
    app.register_blueprint(oauth_bp, url_prefix='/oauth')
    app.extensions['csrf'].exempt(oauth_bp)
    app.cli.add_command(create_client)
