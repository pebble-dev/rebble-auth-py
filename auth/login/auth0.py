from flask import g, current_app
import jwt
from ..models import db
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for, get_state, prepare_state, validate_state

auth0 = auth.remote_app(
    'auth0',
    base_url='https://rebble.eu.auth0.com',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://rebble.eu.auth0.com/oauth/token',
    authorize_url='https://rebble.eu.auth0.com/authorize',
    request_token_params={'scope': 'email profile name openid', 'state': get_state, 'audience': 'https://rebble.eu.auth0.com/api/v2/'},
    app_key='AUTH_IDAAS',
)
auth0.debug = True


@login_blueprint.route("/idaas")
def auth0_auth_start():
    prepare_state()
    return auth0.authorize(callback='https://auth.rebble.watch/auth/idaas/complete') if current_app.debug else auth0.authorize(secure_url_for('.auth0_auth_complete'))


@login_blueprint.route("/idaas/complete")
def auth0_auth_complete():
    validate_state()
    resp = auth0.authorized_response()
    if resp is None:
        print("No response received from Auth0")
        return 'Failed.'
    
    g.auth0_token = (resp['access_token'],)
    token_info = jwt.decode(resp['id_token'], verify=False, options={'verify_signature': False}, algorithms=["RS256"])
    idp_user_id = token_info['sub']
    email = token_info['email']
    name = token_info['nickname']
    response = complete_auth_flow(auth0.name, idp_user_id, name, email)
    db.session.commit()
    return response


@auth0.tokengetter
def get_token():
    return g.auth0_token