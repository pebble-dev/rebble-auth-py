import datetime

from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user

from auth import db
from auth.models import User, UserIdentity, WizardAuditLog
from auth.settings import config

from flask.cli import with_appcontext
import click

wizard_blueprint = Blueprint("wizard", __name__)

def ensure_wizard():
    if not current_user.is_wizard:
        abort(401, 'Hmm... how did you get here?')

@wizard_blueprint.route("/")
@login_required
def wizard_root():
    ensure_wizard()
    return 'OK'

@click.command('make_wizard')
@with_appcontext
@click.argument('idp_name')
@click.argument('idp_user_id')
def make_wizard(idp_name, idp_user_id):
    identity = UserIdentity.query.filter_by(idp=idp_name, idp_user_id=idp_user_id).one()
    user = identity.user

    user.is_wizard = True    
    db.session.commit()
    
    print(f"Ok, made {user.name} <{user.email}> a wizard.")

def init_app(app):
    app.register_blueprint(wizard_blueprint, url_prefix='/wizard')
    app.cli.add_command(make_wizard)
