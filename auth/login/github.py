from ..models import db
from ..settings import config
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for, authorize_access_token

github = auth.register(
    'github',
    client_id=config['AUTH_GITHUB']['consumer_key'],
    client_secret=config['AUTH_GITHUB']['consumer_secret'],
    api_base_url='https://api.github.com/',
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    client_kwargs={'scope': 'user:email', 'token_endpoint_auth_method': 'client_secret_post'},
)


@login_blueprint.route("/github")
def github_auth_start():
    return github.authorize_redirect(secure_url_for('.github_auth_complete'))


@login_blueprint.route("/github/complete")
def github_auth_complete():
    token = authorize_access_token(github)
    if token is None or token.get('access_token') is None:
        return 'Failed.'
    me = github.get('user', token=token).json()
    me_emails = github.get('user/emails', token=token).json()
    email = [x for x in me_emails if x["primary"]][0]["email"]
    response = complete_auth_flow(github.name, str(me["id"]), me["name"], email)
    db.session.commit()
    return response
