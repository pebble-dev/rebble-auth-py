from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user

from auth import db
from auth.models import User, UserIdentity, WizardAuditLog
from auth.settings import config

from flask.cli import with_appcontext
import click

wizard_blueprint = Blueprint("wizard", __name__)

def format_datetime(value, format='%B %-d %Y, %H:%M:%S'):
    return value.strftime(format)

def ensure_wizard():
    if not current_user.is_wizard:
        abort(401, 'Hmm... how did you get here?')

def audit(str):
    event = WizardAuditLog(user = current_user, timestamp = datetime.now(), what = str)
    db.session.add(event)
    db.session.commit()

@wizard_blueprint.route("/")
@login_required
def wizard_root():
    ensure_wizard()
    
    # Wizard audit events.
    audit_events = WizardAuditLog.query \
                                 .filter(WizardAuditLog.timestamp > (datetime.now() - timedelta(hours = 24))) \
                                 .order_by(WizardAuditLog.timestamp.desc()) \
                                 .all()
    
    audit("Logged in as wizard.")
    
    return render_template('wizard/index.html', audit_events = audit_events)

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
    app.jinja_env.filters['format_datetime'] = format_datetime
    app.cli.add_command(make_wizard)
