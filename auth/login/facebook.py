from ..models import db
from ..settings import config
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for, authorize_access_token

facebook = auth.register(
    'facebook',
    client_id=config['AUTH_FACEBOOK']['consumer_key'],
    client_secret=config['AUTH_FACEBOOK']['consumer_secret'],
    api_base_url='https://graph.facebook.com/',
    access_token_url='https://graph.facebook.com/v3.0/oauth/access_token',
    authorize_url='https://www.facebook.com/v3.0/dialog/oauth',
    client_kwargs={'scope': 'email', 'token_endpoint_auth_method': 'client_secret_post'},
)


@login_blueprint.route("/facebook")
def facebook_auth_start():
    return facebook.authorize_redirect(secure_url_for('.facebook_auth_complete'))


@login_blueprint.route("/facebook/complete")
def facebook_auth_complete():
    token = authorize_access_token(facebook)
    if token is None or token.get('access_token') is None:
        return 'Failed.'
    me = facebook.get('me?fields=id,name,email', token=token).json()
    response = complete_auth_flow(facebook.name, me["id"], me["name"], me.get('email',  None))
    db.session.commit()
    return response
