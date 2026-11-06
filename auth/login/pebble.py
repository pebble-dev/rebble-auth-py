from functools import wraps
import os
import random
import time
from uuid import getnode

from flask import request
from flask_login import current_user

from ..models import db


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
