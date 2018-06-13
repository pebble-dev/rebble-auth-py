from flask import g

from ..models import db
from .base import auth, login_blueprint, complete_auth_flow, secure_url_for, prepare_state, validate_state, get_state

github = auth.remote_app(
    'github',
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    request_token_params={'scope': 'user:email', 'state': get_state},
    app_key='AUTH_GITHUB',
)


@login_blueprint.route("/github")
def github_auth_start():
    prepare_state()
    return github.authorize(secure_url_for('.github_auth_complete'))


@login_blueprint.route("/github/complete")
def github_auth_complete():
    validate_state()
    resp = github.authorized_response()
    if resp is None or resp.get('access_token') is None:
        return 'Failed.'
    g.github_token = (resp['access_token'], '')
    me = github.get('user').data
    me_emails = github.get('user/emails').data
    email = [x for x in me_emails if x["primary"]][0]["email"]
    response = complete_auth_flow(github.name, str(me["id"]), me["name"], email)
    db.session.commit()
    return response


@github.tokengetter
def get_token():
    return g.github_token
