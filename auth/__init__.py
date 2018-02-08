from flask import Flask
from flask_login import login_required

from .models import init_app as init_db
from .login import init_app as init_login
from .login.pebble import ensure_pebble
from .oauth import init_app as init_oauth
from .api import init_app as init_api

from .settings import config


app = Flask(__name__)
app.config.update(**config)
init_db(app)
init_login(app)
init_oauth(app)
init_api(app)


@app.route("/")
@login_required
@ensure_pebble
def root():
    return 'hi there'
