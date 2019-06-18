import os

from flask import render_template, request, abort, Blueprint

from ..models import db
from .base import login_blueprint, complete_auth_flow, prepare_state, validate_state, get_state

dummy = None

if os.environ.get('FLASK_ENV', 'production') == 'development':
    @login_blueprint.route("/dummy")
    def dummy_auth_start():
        prepare_state()
        return render_template("dummy.html", state = get_state())


    @login_blueprint.route("/dummy/complete", methods=["POST"])
    def dummy_auth_complete():
        validate_state()
        response = complete_auth_flow('dummy', request.form['user_id'], request.form['name'], request.form['email'])
        db.session.commit()
        return response
