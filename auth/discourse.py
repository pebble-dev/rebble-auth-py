import pydiscourse
from pydiscourse.sso import sso_validate, sso_payload

from flask import Blueprint, request, abort, redirect, render_template
from flask_login import login_required, current_user

from auth.models import db, User
from auth.settings import config

discourse_blueprint = Blueprint("discourse", __name__)

@discourse_blueprint.route("/", methods=['GET', 'POST'])
@login_required
def discourse_sso_view():
    payload = request.args.get('sso')
    signature = request.args.get('sig')
    try:
        nonce = sso_validate(payload, signature, config['DISCOURSE_SECRET'])
    except pydiscourse.exceptions.DiscourseError:
        abort(401, 'No SSO payload or signature.')

    if request.method == 'GET':
        return render_template('discourse.html', user=current_user)
    else:
        if 'deny' in request.form:
            return redirect(config['DISCOURSE_URL'])

        username = request.form.get('username')
        if username and username != '':
            if current_user.username:
                abort(400, 'You already have a username set on the Rebble Developer Forum.')
            if not User.is_valid_username(username):
                abort(400, 'Username must only contain letters, numbers, dashes, dots and underscores, and must not be a system username.')
            if User.query.filter_by(username=username).count() != 0:
                abort(400, 'Username is already taken.')
            User.query.filter_by(id=current_user.id).update({'username': username})
            db.session.commit()
        elif not current_user.username:
            abort(400, 'You need to choose a username.')

    url = sso_redirect_url(nonce, current_user)
    return redirect(config['DISCOURSE_URL'] + url)

def sso_redirect_url(nonce, user):
    attributes = {
        'nonce': nonce,
        'email': user.email,
        'external_id': user.id,
        'name': user.name,
        'username': user.username
    }

    if user.is_wizard:
        attributes['admin'] = 'true'

    add_groups = []
    remove_groups = []

    if user.has_active_sub:
        add_groups.append('subscribers')
    else:
        remove_groups.append('subscribers')

    if user.pebble_dev_portal_uid:
        # TODO: Check if the user has any public apps
        add_groups.append('developers')
        attributes['website'] = f"https://apps.rebble.io/developer/{user.pebble_dev_portal_uid}"

    if add_groups != []:
        attributes['add_groups'] = ','.join(add_groups)
    if remove_groups != []:
        attributes['remove_groups'] = ','.join(remove_groups)
    return "/session/sso_login?%s" % sso_payload(config['DISCOURSE_SECRET'], **attributes)

def init_app(app):
    app.register_blueprint(discourse_blueprint, url_prefix='/discourse')
