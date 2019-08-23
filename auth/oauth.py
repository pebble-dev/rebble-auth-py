from datetime import datetime, timedelta
import logging

from flask import Blueprint, abort, render_template, request, redirect
from flask_oauthlib.provider import OAuth2Provider
from oauthlib.common import generate_token as generate_random_token
from flask_login import current_user, login_required

from auth.login.base import demand_pebble
from .models import db, IssuedToken, AuthClient, User
from .redis import client as redis
import json

from flask.cli import with_appcontext
import click

oauth_bp = Blueprint('oauth_bp', __name__)
oauth = OAuth2Provider()


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


@oauth.grantgetter
def load_grant(client_id, code):
    return Grant.deserialise(redis.get(Grant.redis_key(client_id, code)))


@oauth.grantsetter
def set_grant(client_id, code, request, *args, **kwargs):
    if not current_user.is_authenticated:
        logging.error("Tried to set a grant for a user who is not logged in!?")
        return None
    grant = Grant(client_id, code['code'], current_user.id, request.scopes, request.redirect_uri)
    redis.setex(grant.key, 100, grant.serialise())
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

    db.session.add(token)
    db.session.commit()
    return token


@oauth.clientgetter
def get_client(client_id):
    return AuthClient.query.filter_by(client_id=client_id).one()


@oauth_bp.route('/authorise', methods=['GET', 'POST'])
@login_required
@oauth.authorize_handler
def authorise(*args, **kwargs):
    if request.method == 'GET':
        client_id = kwargs.get('client_id')
        client = AuthClient.query.filter_by(client_id=client_id).one()
        kwargs['client'] = client
    
        if client.is_rws:
            return True
            
        return render_template('oauthorise.html', **kwargs)
    
    return 'confirm' in request.form

@oauth_bp.route('/token', methods=['GET', 'POST'])
@oauth.token_handler
def access_token():
    return None


@oauth_bp.route('/error')
def oauth_error():
    return render_template('oauth-error.html',
                           error=request.args.get('error', 'unknown'),
                           error_description=request.args.get('error_description', '')), 400


def generate_token(request, refresh_token=False):
    return generate_random_token()

@click.command('create_oauth_client')
@with_appcontext
@click.argument('name')
@click.option('--redirect_uri', multiple=True, required=True)
@click.option('--is_rws', is_flag=True)
@click.option('--confidential', is_flag=True)
@click.option('--scope', multiple=True)
def create_client(name, redirect_uri, confidential, scope, is_rws):
    client_id = generate_random_token(length = 24)
    client_secret = 'secret_%s' % generate_random_token(length = 32)
    
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
    app.config['OAUTH2_PROVIDER_TOKEN_EXPIRES_IN'] = 315576000  # 10 years
    app.config['OAUTH2_PROVIDER_ERROR_ENDPOINT'] = 'oauth_bp.oauth_error'
    oauth.init_app(app)
    app.register_blueprint(oauth_bp, url_prefix='/oauth')
    app.extensions['csrf'].exempt(oauth_bp)
    app.cli.add_command(create_client)
