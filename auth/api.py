import datetime
from flask import Blueprint, request, jsonify, abort
from oauthlib.common import generate_token

from auth.models import IssuedToken, db
from .oauth import oauth
from .login.pebble import api_ensure_pebble

api = Blueprint('api', __name__)


@api.route('/me')
@oauth.require_oauth('profile')
def me():
    if request.args.get('flag_authed') == 'true':
        if not request.oauth.user.has_logged_in:
            request.oauth.user.has_logged_in = True
            db.session.commit()
    return jsonify(
        uid=request.oauth.user.id,
        name=request.oauth.user.name,
        is_subscribed=request.oauth.user.has_active_sub,
        scopes=request.oauth.scopes,
        is_wizard=request.oauth.user.is_wizard,
        has_timeline=request.oauth.user.has_timeline,
        timeline_ttl=request.oauth.user.timeline_ttl
    )


@api.route('/me/token')
@oauth.require_oauth()
def token_info():
    return jsonify(scopes=request.oauth.scopes)


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


@api.route('/dictation-token')
@oauth.require_oauth('pebble')
def get_dictation_token():
    user = request.oauth.user
    asr_token = IssuedToken.query.filter_by(user_id=user.id, scopes='{asr}').first()
    if not asr_token:
        asr_token = IssuedToken(user_id=user.id, client_id='asr', scopes=['asr'],
                                expires=datetime.datetime.utcnow() + datetime.timedelta(days=3650),
                                access_token=generate_token(15, 'abcdefghijklmnopqrsstuvwxyz0123456789'), refresh_token=generate_token())
        db.session.add(asr_token)
        db.session.commit()
    return jsonify(token=asr_token.access_token)


def init_app(app, url_prefix='/api/v1'):
    app.register_blueprint(api, url_prefix=url_prefix)
    app.extensions['csrf'].exempt(api)
