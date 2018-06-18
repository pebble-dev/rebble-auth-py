from flask import render_template, request, abort

from ..models import db
from .base import login_blueprint, complete_auth_flow

dummy = None


@login_blueprint.route("/dummy")
def dummy_auth_start():
    if not app.config['DEVELOPMENT_MODE']:
        abort(404)
    return render_template("dummy.html")


@login_blueprint.route("/dummy/complete", methods=["POST"])
def dummy_auth_complete():
    if not app.config['DEVELOPMENT_MODE']:
        abort(404)
    response = complete_auth_flow('dummy', request.form['user_id'], request.form['name'], request.form['email'])
    db.session.commit()
    return response
