from datetime import datetime, timedelta

import stripe
from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user

from auth import db
from auth.models import User, UserIdentity, WizardAuditLog
from auth.settings import config

from flask.cli import with_appcontext
import click

stripe.api_key = config['STRIPE_SECRET_KEY']
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
    db.session.commit()
    
    return render_template('wizard/user_search.html', users = users, search = search)

@wizard_blueprint.route("/user/<id>")
@login_required
def user_by_id(id):
    ensure_wizard()
    
    user = User.query.filter_by(id = id).one()
    identities = UserIdentity.query.filter_by(user=user).all()
    subscription = None
    if user.stripe_subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
        except stripe.error.InvalidRequestError:
            pass
    
    audit(f"Viewed user {id}")

    return render_template('wizard/user.html', user = user, identities = identities, subscription = subscription)

@wizard_blueprint.route("/user/<id>/modify", methods=["POST"])
@login_required
def user_modify(id):
    ensure_wizard()
    
    user = User.query.filter_by(id = id).one()
    
    if 'name' in request.form:
        what = 'name'
        old = user.name
        new = request.form['name']
        user.name = new
    elif 'email' in request.form:
        what = 'e-mail address'
        old = user.email
        new = request.form['email']
        user.email = new
    
    audit(f"MODIFICATION: Changed user {user.id} {what} from '{old}' to '{new}'")
    db.session.commit()
    
    return render_template('wizard/user_modify.html', user = user, what = what, old = old, new = new)

@wizard_blueprint.route("/user/<id>/movesubscription", methods=["GET", "POST"])
@login_required
def user_movesubscription(id):
    ensure_wizard()
    
    olduser = User.query.filter_by(id = id).one()
    
    if request.method == "GET":
        dest = request.args.get("dest")
    else:
        dest = request.form.get("dest")
    destuser = User.query.filter_by(id = dest).one()

    possible = olduser.has_active_sub and not destuser.has_active_sub
    if request.method == 'POST' and possible:
        destuser.stripe_customer_id = olduser.stripe_customer_id
        destuser.stripe_subscription_id = olduser.stripe_subscription_id
        destuser.subscription_expiry = olduser.subscription_expiry
        
        olduser.stripe_customer_id = None
        olduser.stripe_subscription_id = None
        olduser.subscription_expiry = None
        
        audit(f"MODIFICATION: Moved subscription from user {olduser.id} to user {destuser.id}")
        db.session.commit()
    
    return render_template('wizard/user_movesubscription.html', olduser = olduser, destuser = destuser, possible = possible, prompt = request.method == "GET")

@wizard_blueprint.route("/useridentity/<id>")
@login_required
def useridentity_by_idp(id):
    ensure_wizard()
    
    idp, idp_user_id = id.split(':', 1)
    identity = UserIdentity.query.filter_by(idp = idp, idp_user_id = idp_user_id).one()
    
    audit(f"Viewed useridentity {id}")

    return render_template('wizard/useridentity.html', identity = identity)


@wizard_blueprint.route("/useridentity/<id>/moveto", methods=["GET", "POST"])
@login_required
def useridentity_moveto(id):
    ensure_wizard()
    
    idp, idp_user_id = id.split(':', 1)
    identity = UserIdentity.query.filter_by(idp = idp, idp_user_id = idp_user_id).one()
    
    if request.method == "GET":
        dest = request.args.get("dest")
    else:
        dest = request.form.get("dest")
    olduser = identity.user
    destuser = User.query.filter_by(id = dest).one()
    nidentities = UserIdentity.query.filter_by(user = identity.user).count()
    
    if request.method == "POST":
        audit(f"MODIFICATION: Moved identity {idp}:{idp_user_id} from user {olduser.id} to user {destuser.id}.")
        identity.user = destuser
        db.session.commit()
    
    return render_template('wizard/useridentity_move.html', identity = identity, olduser = olduser, destuser = destuser, nidentities = nidentities, prompt = request.method == "GET")

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
