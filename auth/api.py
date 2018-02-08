from flask import Blueprint, request, jsonify, abort
from .oauth import oauth
from .login.pebble import api_ensure_pebble

api = Blueprint('api', __name__)


@api.route('/me')
@oauth.require_oauth('profile')
def me():
    return jsonify(uid=request.oauth.user.id)


@api.route('/me/pebble/auth')
@oauth.require_oauth('pebble')
@api_ensure_pebble
def pebble_auth_me():
    user = request.oauth.user
    return jsonify(id=user.pebble_auth_uid, email=user.email, name=user.name)


@api.route('/me/pebble/dev-portal')
@oauth.require_oauth('pebble')
@api_ensure_pebble
def pebble_dev_portal_me():
    user = request.oauth.user
    return jsonify([{'id': user.pebble_dev_portal_uid, 'uid': user.pebble_auth_uid}])


def init_app(app, url_prefix='/api/v1'):
    app.register_blueprint(api, url_prefix=url_prefix)
