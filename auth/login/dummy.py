import os

from flask import render_template, request, abort, Blueprint

from ..models import db
from .base import login_blueprint, complete_auth_flow

dummy = None

if os.environ.get('FLASK_ENV', 'production') == 'development':
    @login_blueprint.route("/dummy")
    def dummy_auth_start():
        return render_template("dummy.html")


    @login_blueprint.route("/dummy/complete", methods=["POST"])
    def dummy_auth_complete():
        response = complete_auth_flow('dummy', request.form['user_id'], request.form['name'], request.form['email'])
        db.session.commit()
        return response
