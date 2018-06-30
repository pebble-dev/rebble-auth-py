from functools import wraps
import os
import random
import time
from uuid import getnode

from flask import request, abort, redirect, url_for, session
from flask_login import current_user, login_required

from flask import g

from flask import current_app

from ..models import db
from .base import auth, login_blueprint, secure_url_for, redirect_next, get_state, prepare_state, validate_state

pebble = auth.remote_app(
    'pebble',
    base_url='https://auth.getpebble.com/api/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://auth.getpebble.com/oauth/token',
    authorize_url='https://auth.getpebble.com/oauth/authorize',
    app_key='AUTH_PEBBLE',
    request_token_params={'state': get_state},
)


@pebble.tokengetter
def get_token():
    return current_user.pebble_token,


@login_blueprint.route("/pebble")
@login_required
def pebble_auth_start():
    prepare_state()
    if current_app.env == 'development':
        return pebble.authorize('http://localhost:60000')
    else:
        return pebble.authorize(secure_url_for('.pebble_auth_complete'))


@login_blueprint.route("/pebble/complete")
@login_required
def pebble_auth_complete():
    validate_state()
    resp = pebble.authorized_response()
    if resp is None:
        return 'Failed.'
    current_user.pebble_token = resp['access_token']
    user_info = pebble.request('me.json').data
    current_user.pebble_auth_uid = user_info['id']
    store_info = pebble.request('https://dev-portal.getpebble.com/api/users/me').data
    current_user.pebble_dev_portal_uid = store_info['users'][0]['id']
    db.session.commit()
    return redirect_next()


# This generates a MongoDB-style ObjectID, which is what all Pebble identifiers are.
class ObjectIdGenerator:
    def __init__(self):
        self.counter = random.randint(0, 0xFFFFFF)
        self.node_id = getnode() % 0xFFFFFF
        self.pid = os.getpid() % 0xFFFF

    def generate(self):
        self.counter = (self.counter + 1) % 0xFFFFFF
        return f'{(int(time.time()) % 0xFFFFFFFF):08x}{self.node_id:06x}{self.pid:04x}{self.counter:06x}'


id_generator = ObjectIdGenerator()


def generate_pebble_ids(user):
    must_commit = False
    if user.pebble_dev_portal_uid is None:
        user.pebble_dev_portal_uid = id_generator.generate()
        must_commit = True
    if user.pebble_auth_uid is None:
        user.pebble_auth_uid = id_generator.generate()
        must_commit = True
    if must_commit:
        db.session.commit()


def api_ensure_pebble(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        generate_pebble_ids(request.oauth.user)
        return fn(*args, **kwargs)
    return wrapper


def ensure_pebble(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        generate_pebble_ids(current_user)
        return fn(*args, **kwargs)
    return wrapper
