from ..models import db
from ..settings import config
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for, authorize_access_token

google = auth.register(
    'google',
    client_id=config['AUTH_GOOGLE']['consumer_key'],
    client_secret=config['AUTH_GOOGLE']['consumer_secret'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile', 'token_endpoint_auth_method': 'client_secret_post'},
)


@login_blueprint.route("/google")
def google_auth_start():
    return google.authorize_redirect(secure_url_for('.google_auth_complete'))


@login_blueprint.route("/google/complete")
def google_auth_complete():
    token = authorize_access_token(google)
    if token is None:
        return 'Failed.'
    token_info = token['userinfo']
    idp_user_id = token_info['sub']
    email = token_info['email'] if token_info['email_verified'] else None
    name = token_info.get('name') or google.userinfo(token=token).get('name')
    response = complete_auth_flow(google.name, idp_user_id, name, email)
    db.session.commit()
    return response
