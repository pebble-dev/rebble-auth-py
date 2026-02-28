import datetime
from flask import Blueprint, request, jsonify, abort
from oauthlib.common import generate_token
from werkzeug.exceptions import BadRequest
from sqlalchemy.orm.exc import NoResultFound

from auth.models import IssuedToken, db, User, UserIdentity, WizardAuditLog
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
        timeline_ttl=request.oauth.user.timeline_ttl,
        boot_overrides=request.oauth.user.boot_overrides
    )


@api.route('/me/token')
@oauth.require_oauth()
def token_info():
    user = request.oauth.user
    return jsonify(
        scopes=request.oauth.scopes,
        uid=user.id,
        is_subscribed=user.has_active_sub,
        audio_debug_mode=user.audio_debug_mode_enabled)


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
        'rebble_username': user.username,
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

@api.route('/wizard/getuserfromidentity/<id>')
@oauth.require_oauth()
def wizard_get_user_by_identity(id):
    ensure_wizard()

    try:
        idp, idp_user_id = id.split(':', 1)
        identity = UserIdentity.query.filter_by(idp = idp, idp_user_id = idp_user_id).one()
    except NoResultFound:
        return jsonify(error="Unknown user identity", e="identity.notfound"), 404
    except Exception:
        return jsonify(error="An unknown error occured", e="error.general", message="An error ocurred retrieving the user. Is the identity string valid?"), 500

    audit(f"Viewed useridentity {id}", request.oauth.user)

    return jsonify({
        'user_name': identity.user.name,
        'user_email': identity.user.email,
        'pebble_auth_uid': identity.user.pebble_auth_uid,
        'pebble_dev_portal_uid': identity.user.pebble_dev_portal_uid,
        'pebble_token': identity.user.pebble_token,
        'has_logged_in': identity.user.has_logged_in,
        'account_type': identity.user.account_type,
        'stripe_customer_id': identity.user.stripe_customer_id,
        'stripe_subscription_id': identity.user.stripe_subscription_id,
        'subscription_expiry': identity.user.subscription_expiry,
        'is_wizard': identity.user.is_wizard,
        'boot_overrides': identity.user.boot_overrides,
        'audio_debug_mode': identity.user.audio_debug_mode,
        'username': identity.user.username,
        'id': identity.user.id
    })

@api.route('/wizard/setdeveloperid', methods=["POST"])
@oauth.require_oauth()
def wizard_update_user_developer_id():
    ensure_wizard()

    try:
        req = request.json
    except BadRequest:
        return jsonify(error="Invalid POST body. Expected JSON", e="body.invalid"), 400

    if req is None:
        return jsonify(error="Invalid POST body. Expected JSON and 'Content-Type: application/json'", e="request.invalid"), 400

    if not "user_id" in req:
        return jsonify(error="Missing required field: user_id", e="missing.field.user_id"), 400

    if not "developer_id" in req:
        return jsonify(error="Missing required field: developer_id", e="missing.field.developer_id"), 400

    try:
        user = User.query.filter_by(id = req["user_id"]).one()
    except NoResultFound:
        return jsonify(error="Invalid user ID", e="invalid.field.user_id"), 400
    except Exception:
        return jsonify(error="An unknown error occured", e="error.general", message="An error ocurred retrieving the user. Is the ID valid?"), 500

    old_developer_id = user.pebble_dev_portal_uid
    user.pebble_dev_portal_uid = req["developer_id"]
    db.session.commit()

    audit(f"API MODIFICATION: Changed user {user.id} developer ID from '{old_developer_id}' to '{user.pebble_dev_portal_uid}'", request.oauth.user)

    return jsonify({
        'user_id': user.id,
        'user_name': user.name,
        'developer_id': user.pebble_dev_portal_uid
    })

def ensure_wizard():
    if not request.oauth.user.is_wizard:
        abort(401, 'Hmm... how did you get here?')

def audit(str, current_user):
    event = WizardAuditLog(user = current_user, timestamp = datetime.datetime.now(), what = str)
    db.session.add(event)
    db.session.commit()

def init_app(app, url_prefix='/api/v1'):
    app.register_blueprint(api, url_prefix=url_prefix)
    app.extensions['csrf'].exempt(api)
