from flask import url_for, g

from ..models import db
from .base import auth, login_blueprint, complete_auth_flow

twitter = auth.remote_app(
    name='twitter',
    base_url='https://api.twitter.com/1.1/',
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
    return twitter.authorize(url_for('login.twitter_auth_complete', _external=True))


@login_blueprint.route("/twitter/complete")
def twitter_auth_complete():
    resp = twitter.authorized_response()
    if resp is None:
        return 'Failed.'
    g.twitter_token = (resp['oauth_token'], resp['oauth_token_secret'])
    user_info = twitter.request('account/verify_credentials.json?include_entities=false&skip_status=true&include_email=true').data
    response = complete_auth_flow(twitter.name, resp['user_id'], user_info['name'], user_info['email'])
    db.session.commit()
    return response
