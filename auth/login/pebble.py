from functools import wraps
import os
import random
import time
from uuid import getnode

from flask import request, abort, redirect, url_for, session
from flask_login import current_user, login_required
from ..models import db

from flask import g

from ..models import db
from .base import auth, login_blueprint, secure_url_for

pebble = auth.remote_app(
    'pebble',
    base_url='https://auth.getpebble.com/api/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://auth.getpebble.com/oauth/token',
    authorize_url='https://auth.getpebble.com/oauth/authorize',
    app_key='AUTH_PEBBLE',
)


@pebble.tokengetter
def get_token():
    return g.pebble_token


@login_blueprint.route("/pebble")
@login_required
def pebble_auth_start():
    return pebble.authorize(secure_url_for('.pebble_auth_complete'))


@login_blueprint.route("/pebble/complete")
@login_required
def pebble_auth_complete():
    resp = pebble.authorized_response()
    if resp is None:
        return 'Failed.'
    g.pebble_token = (resp['access_token'],)
    current_user.pebble_token = resp['access_token']
    user_info = pebble.request('me.json').data
    current_user.pebble_auth_uid = user_info['id']
    store_info = pebble.request('https://dev-portal.getpebble.com/api/users/me').data
    current_user.pebble_dev_portal_uid = store_info['users'][0]['id']
    db.session.commit()
    return redirect(session.get('next') or '/')


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


def api_ensure_pebble(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = request.oauth.user
        if user.pebble_auth_uid is None or user.pebble_dev_portal_uid is None:
            return abort(401)
        else:
            return fn(*args, **kwargs)
    return wrapper


def ensure_pebble(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user
        if user.pebble_auth_uid is None or user.pebble_dev_portal_uid is None:
            return redirect(url_for('login.demand_pebble'))
        else:
            return fn(*args, **kwargs)
    return wrapper
