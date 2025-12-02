import pydiscourse
from pydiscourse.sso import sso_validate, sso_payload

from flask import Blueprint, request, abort, redirect
from flask_login import login_required, current_user

from auth.settings import config

discourse_blueprint = Blueprint("discourse", __name__)

@discourse_blueprint.route("/")
@login_required
def discourse_sso_view():
    payload = request.args.get('sso')
    signature = request.args.get('sig')
    try:
        nonce = sso_validate(payload, signature, config['DISCOURSE_SECRET'])
    except pydiscourse.exceptions.DiscourseError:
        abort(401, 'No SSO payload or signature.')
    url = sso_redirect_url(nonce, current_user)
    return redirect(config['DISCOURSE_URL'] + url)

def sso_redirect_url(nonce, user):
    attributes = {
        'nonce': nonce,
        'email': user.email,
        'external_id': user.id,
        'name': user.name
    }

    if user.is_wizard:
        attributes['admin'] = 'true'

    add_groups = []
    remove_groups = []

    if user.has_active_sub:
        add_groups.append('subscriber')
    else:
        remove_groups.append('subscriber')

    if user.pebble_dev_portal_uid:
        # TODO: Check if the user has any public apps
        add_groups.append('developer')
        attributes['website'] = f"https://apps.rebble.io/developer/{user.pebble_dev_portal_uid}"

    if add_groups != []:
        attributes['add_groups'] = '['+','.join(add_groups)+']'
    if remove_groups != []:
        attributes['remove_groups'] = '['+','.join(remove_groups)+']'
    return "/session/sso_login?%s" % sso_payload(config['DISCOURSE_SECRET'], **attributes)

def init_app(app):
    app.register_blueprint(discourse_blueprint, url_prefix='/discourse')
