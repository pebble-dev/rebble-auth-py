import datetime

import stripe
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user

from auth import db
from auth.models import User, UserIdentity
from auth.settings import config

import json

stripe.api_key = config['STRIPE_SECRET_KEY']
billing_blueprint = Blueprint("billing", __name__)


def format_ts(value, format='%B %-d, %Y'):
    return datetime.datetime.utcfromtimestamp(value).strftime(format)


@billing_blueprint.route('/account/')
@login_required
def account_info(message = None):
    # Look up where they came from, too, so we can remind them.
    identities = UserIdentity.query.filter_by(user=current_user).all()

    subscription = None
    if current_user.stripe_subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
        except stripe.error.InvalidRequestError:
            pass
    return render_template('account-info.html',
                           user=current_user, subscription=subscription,
                           monthly_plan=config['STRIPE_MONTHLY_PLAN'],
                           annual_plan=config['STRIPE_ANNUAL_PLAN'],
                           stripe_key=config['STRIPE_PUBLIC_KEY'],
                           identities=identities,
                           message=message)


def handle_card_error(e: stripe.error.CardError):
    return str(e)


@billing_blueprint.route('/account/sub/create', methods=['POST'])
@login_required
def create_subscription():
    plan = request.form['plan']
    customer = None
    if current_user.stripe_customer_id:
        customer = stripe.Customer.retrieve(current_user.stripe_customer_id)
        if ('deleted' not in customer) or (not customer.deleted):
            customer.source = request.form['stripeToken']
            try:
                customer.save()
            except (stripe.error.CardError, stripe.error.InvalidRequestError) as e:
                return handle_card_error(e)
        else:
            customer = None
    if customer is None:
        try:
            customer = stripe.Customer.create(
                description=f"{current_user.name or '(no name)'} (#{current_user.id})",
                email=f"{current_user.email}",
                source=request.form['stripeToken'],
                metadata={
                    'user_id': current_user.id,
                }
            )
        except stripe.error.CardError as e:
            return handle_card_error(e)
        current_user.stripe_customer_id = customer.stripe_id
    start_date = None
    to_cancel = None
    if current_user.stripe_subscription_id:
        sub = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
        if sub.status != "canceled":
            # In this case we have an active subscription and are changing the billing
            # frequency. We need to delete the old item and create a new one.
            to_cancel = sub
            start_date = sub.current_period_end
    try:
        sub = stripe.Subscription.create(
            customer=customer.stripe_id,
            items=[{"plan": plan}],
            trial_end=start_date,
        )
    except (stripe.error.CardError, stripe.error.InvalidRequestError) as e:
        return handle_card_error(e)
    current_user.stripe_subscription_id = sub.stripe_id
    current_user.subscription_expiry = datetime.datetime.utcfromtimestamp(sub.current_period_end).replace(tzinfo=datetime.timezone.utc) + datetime.timedelta(days=1)
    db.session.commit()
    if to_cancel:
        to_cancel.delete()
    return redirect(url_for('.account_info'))

@billing_blueprint.route('/account/sub/update', methods=['POST'])
@login_required
def update_credit_card():
    try:
        customer = stripe.Customer.modify(
            current_user.stripe_customer_id,
            source = request.form['stripeToken']
        )
    except (stripe.error.CardError, stripe.error.InvalidRequestError) as e:
        return handle_card_error(e)
    
    return redirect(url_for('.update_complete'))

@billing_blueprint.route('/account/sub/update_complete')
@login_required
def update_complete():
    return account_info('Okay, updated your credit card.')

@billing_blueprint.route('/account/sub/delete', methods=["POST"])
def cancel_subscription():
    sub = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
    sub.delete(at_period_end=True)
    return redirect(url_for('.account_info'))

@billing_blueprint.route('/account/boot_overrides', methods=["POST"])
@login_required
def boot_overrides():
    try:
        overrides = json.loads(request.form['overrides'])
    except Exception as e:
        return str(e), 400
    
    current_user.boot_overrides = overrides
    db.session.commit()
    
    return "Okay, did that.  You can hit the back and refresh buttons on your own, since you're a developer, after all.  Make sure to rerun boot to pick up the new changes."

@billing_blueprint.route('/account/set_audio_debug_mode', methods=["POST"])
@login_required
def set_audio_debug_mode():
    should_enable = request.form.get('enable') == 'true'
    if should_enable:
        current_user.audio_debug_mode = datetime.datetime.now()
    else:
        current_user.audio_debug_mode = None
    db.session.commit()
    return redirect(url_for('.account_info'))

@billing_blueprint.route('/stripe/event', methods=["POST"])
def stripe_event():
    payload = request.data
    signature = request.headers['Stripe-Signature']
    try:
        event = stripe.Webhook.construct_event(payload, signature, config['STRIPE_WEBHOOK_KEY'])
    except ValueError:
        return '???', 400
    except stripe.error.SignatureVerificationError:
        return 'signature verification failed', 400

    if event.type == "invoice.payment_succeeded":
        # try and figure out if we care about this.
        results = []
        for line in event.data.object.lines.data:
            if line.subscription:
                user = User.query.filter_by(stripe_subscription_id=line.subscription).one_or_none()
                if user is not None:
                    user.subscription_expiry = datetime.datetime.utcfromtimestamp(line.period.end) + datetime.timedelta(days=1)
                    db.session.commit()
                    results.append(f"Set expiry date for user #{user.id} to {user.subscription_expiry}.")
        return '\n'.join(results)
    elif event.type == "customer.subscription.deleted":
        user = User.query.filter_by(stripe_subscription_id=event.data.object.id).one_or_none()
        if user is not None:
            user.subscription_expiry = None
            db.session.commit()
            return f'Terminated subscription for user #{user.id}.'

    return ''


def init_app(app, prefix='/'):
    app.register_blueprint(billing_blueprint, url_prefix=prefix)
    app.jinja_env.filters['format_ts'] = format_ts
    app.jinja_env.filters['json_dump'] = json.dumps
    app.extensions['csrf'].exempt(stripe_event)
