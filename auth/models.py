import datetime
import string
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

SUBSCRIBER_ROLLOUT_START = datetime.datetime(2019, 7, 21, 7, 0, 0, 0)
NONSUBSCRIBER_ROLLOUT_START = datetime.datetime(2019, 7, 28, 7, 0, 0, 0)

USERNAME_SET = frozenset(string.ascii_lowercase + string.digits + '-._')

db = SQLAlchemy()
migrate = Migrate()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, nullable=False)
    name = db.Column(db.String)
    pebble_auth_uid = db.Column(db.String(24), nullable=True)
    pebble_dev_portal_uid = db.Column(db.String(24), nullable=True)
    pebble_token = db.Column(db.String, nullable=True, index=True)
    has_logged_in = db.Column(db.Boolean, nullable=False, server_default='false')
    account_type = db.Column(db.Integer, nullable=False, server_default='0')
    stripe_customer_id = db.Column(db.String, nullable=True, index=True)
    stripe_subscription_id = db.Column(db.String, nullable=True, index=True)
    subscription_expiry = db.Column(db.DateTime, nullable=True)
    is_wizard = db.Column(db.Boolean, server_default='false')
    boot_overrides = db.Column(JSONB)
    audio_debug_mode = db.Column(db.DateTime, nullable=True)
    username = db.Column(db.String(24), unique=True, index=True)

    @property
    def has_active_sub(self):
        return self.subscription_expiry is not None and datetime.datetime.utcnow() <= self.subscription_expiry
    
    @property
    def has_timeline(self):
        return self.is_wizard or self.has_active_sub or \
               (datetime.datetime.utcnow() > (NONSUBSCRIBER_ROLLOUT_START + datetime.timedelta(seconds = self.id * 2)))
    
    @property
    def timeline_ttl(self):
        return 15 if self.has_active_sub else (3 * 60)

    @property
    def audio_debug_mode_enabled(self):
        return self.audio_debug_mode is not None and datetime.datetime.now() <= self.audio_debug_mode + datetime.timedelta(days=1)

    @classmethod
    def is_valid_username(cls, username):
        return set(username) <= USERNAME_SET and 4 <= len(username) <= 24


class UserIdentity(db.Model):
    __tablename__ = "user_identities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User')
    idp = db.Column(db.String)
    idp_user_id = db.Column(db.String, nullable=False)
db.Index('user_identity_idp_id_index', UserIdentity.idp, UserIdentity.idp_user_id)


class AuthClient(db.Model):
    __tablename__ = "oauth_clients"
    name = db.Column(db.String)
    client_id = db.Column(db.String(40), primary_key=True)
    client_secret = db.Column(db.String(55), unique=True, index=True, nullable=False)
    redirect_uris = db.Column(ARRAY(db.String))
    is_confidential = db.Column(db.Boolean)
    default_scopes = db.Column(ARRAY(db.String))
    is_rws = db.Column(db.Boolean, server_default='false') # Internal clients do not need confirmation for OAuth.

    @property
    def client_type(self):
        return 'confidential' if self.is_confidential else 'public'

    @property
    def default_redirect_uri(self):
        return self.redirect_uris[0]


class IssuedToken(db.Model):
    __tablename__ = "issued_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User')
    client_id = db.Column(db.String(40), db.ForeignKey('oauth_clients.client_id'), nullable=False)
    client = db.relationship('AuthClient')
    scopes = db.Column(ARRAY(db.String))
    expires = db.Column(db.DateTime)
    access_token = db.Column(db.String, unique=True)
    refresh_token = db.Column(db.String, unique=True)
    token_type = 'bearer'


    def delete(self):
        db.session.delete(self)
        db.session.commit()
        return self


class WizardAuditLog(db.Model):
    __tablename__ = "wizard_audit_log"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User')
    what = db.Column(db.String)


def init_app(app):
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    migrate.init_app(app, db)
