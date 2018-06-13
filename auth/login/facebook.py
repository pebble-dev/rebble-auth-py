from flask import g

from ..models import db
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for, prepare_state, validate_state, get_state

facebook = auth.remote_app(
    'facebook',
    base_url='https://graph.facebook.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://graph.facebook.com/v3.0/oauth/access_token',
    authorize_url='https://www.facebook.com/v3.0/dialog/oauth',
    request_token_params={'scope': 'email', 'state': get_state},
    app_key='AUTH_FACEBOOK',
)


@login_blueprint.route("/facebook")
def facebook_auth_start():
    prepare_state()
    return facebook.authorize(secure_url_for('.facebook_auth_complete'))


@login_blueprint.route("/facebook/complete")
def facebook_auth_complete():
    validate_state()
    resp = facebook.authorized_response()
    if resp is None or resp.get('access_token') is None:
        return 'Failed.'
    g.facebook_token = (resp['access_token'], '')
    me = facebook.get('me?fields=id,name,email').data
    response = complete_auth_flow(facebook.name, me["id"], me["name"], me['email'])
    db.session.commit()
    return response


@facebook.tokengetter
def get_token():
    return g.facebook_token
