from flask import Blueprint, request, jsonify, abort
from .oauth import oauth
from .login.pebble import api_ensure_pebble

api = Blueprint('api', __name__)


@api.route('/me')
@oauth.require_oauth('profile')
def me():
    return jsonify(
        uid=request.oauth.user.id,
        name=request.oauth.user.name,
        is_subscribed=request.oauth.user.has_active_sub,
    )


@api.route('/me/pebble/auth')
@oauth.require_oauth('pebble')
@api_ensure_pebble
def pebble_auth_me():
    user = request.oauth.user
    return jsonify(id=user.pebble_auth_uid, email=user.email, name=user.name)


@api.route('/me/pebble/appstore')
@oauth.require_oauth('pebble')
@api_ensure_pebble
def pebble_dev_portal_me():
    user = request.oauth.user
    return jsonify({
        'id': user.pebble_dev_portal_uid,
        'uid': user.pebble_auth_uid,
        'rebble_id': user.id,
        'name': user.name,
    })


def init_app(app, url_prefix='/api/v1'):
    app.register_blueprint(api, url_prefix=url_prefix)
    app.extensions['csrf'].exempt(api)
