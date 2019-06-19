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

@wizard_blueprint.route("/user/search", methods=["POST"])
@login_required
def user_search():
    ensure_wizard()
    
    if 'email' in request.form:
        search = f"Users with e-mail address {request.form['email']}"
        users = User.query.filter_by(email = request.form['email']).all()
    elif 'name' in request.form:
        search = f"Users with name {request.form['name']}"
        users = User.query.filter_by(name = request.form['name']).all()
    elif 'idp' in request.form:
        search = f"Users logging in as {request.form['idp']}"
        idp, idp_user_id = request.form['idp'].split(':', 1)
        identities = UserIdentity.query.filter_by(idp = idp, idp_user_id = idp_user_id).all()
        users = [x.user for x in identities]
    
    audit(f"Searched for: {search}")
    
    return render_template('wizard/user_search.html', users = users, search = search)

@wizard_blueprint.route("/user/<id>")
@login_required
def user_by_id(id):
    ensure_wizard()
    
    user = User.query.filter_by(id = id).one()
    identities = UserIdentity.query.filter_by(user=user).all()
    subscription = None
    if current_user.stripe_subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
        except stripe.error.InvalidRequestError:
            pass
    
    audit(f"Viewed user {id}")

    return render_template('wizard/user.html', user = user, identities = identities, subscription = subscription)

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
