from ..models import db
from ..settings import config
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for, authorize_access_token

twitter = auth.register(
    'twitter',
    client_id=config['AUTH_TWITTER']['consumer_key'],
    client_secret=config['AUTH_TWITTER']['consumer_secret'],
    api_base_url='https://api.twitter.com/2/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
)


@login_blueprint.route("/twitter")
def twitter_auth_start():
    return twitter.authorize_redirect(secure_url_for('.twitter_auth_complete'))


@login_blueprint.route("/twitter/complete")
def twitter_auth_complete():
    token = authorize_access_token(twitter)
    if token is None:
        return 'Failed.'
    user_info = twitter.get('users/me', token=token).json()
    response = complete_auth_flow(twitter.name, token['user_id'], user_info.get('data', {}).get('name', None), None)
    db.session.commit()
    return response
