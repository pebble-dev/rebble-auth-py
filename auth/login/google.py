from flask import g
import jwt

from ..models import db
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for, get_state, prepare_state, validate_state

google = auth.remote_app(
    'google',
    base_url='https://www.googleapis.com/oauth2/v3/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    request_token_params={'scope': 'email profile', 'state': get_state},
    app_key='AUTH_GOOGLE',
)


@login_blueprint.route("/google")
def google_auth_start():
    prepare_state()
    return google.authorize(secure_url_for('.google_auth_complete'))


@login_blueprint.route("/google/complete")
def google_auth_complete():
    validate_state()
    resp = google.authorized_response()
    if resp is None:
        return 'Failed.'
    g.google_token = (resp['access_token'],)
    token_info = jwt.decode(resp['id_token'], verify=False)
    idp_user_id = token_info['sub']
    email = token_info['email'] if token_info['email_verified'] else None
    name = google.get('userinfo').data['name']
    response = complete_auth_flow(google.name, idp_user_id, name, email)
    db.session.commit()
    return response


@google.tokengetter
def get_token():
    return g.google_token