from flask import g

from ..models import db
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for

twitter = auth.remote_app(
    name='twitter',
    base_url='https://api.twitter.com/2/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
    app_key='AUTH_TWITTER',
)


@twitter.tokengetter
def get_token():
    return g.twitter_token


@login_blueprint.route("/twitter")
def twitter_auth_start():
    return twitter.authorize(secure_url_for('.twitter_auth_complete'))


@login_blueprint.route("/twitter/complete")
def twitter_auth_complete():
    resp = twitter.authorized_response()
    if resp is None:
        return 'Failed.'
    g.twitter_token = (resp['oauth_token'], resp['oauth_token_secret'])
    user_info = twitter.request('users/me').data
    response = complete_auth_flow(twitter.name, resp['user_id'], user_info.get('data', {}).get('name', None), None)
    db.session.commit()
    return response
