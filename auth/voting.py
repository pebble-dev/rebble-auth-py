import random

from flask import Blueprint, request, abort, redirect, render_template, flash, url_for, current_app
from flask_login import login_required, current_user
from datetime import datetime

from auth.models import db, Election, Candidate, Vote, VoteReceipt

voting_blueprint = Blueprint("voting", __name__)

@voting_blueprint.route("/", methods=['GET'])
@login_required
def elections():
    elections = Election.query.all()
    return render_template('elections.html', elections=elections, now=datetime.now(), current_user=current_user)

@voting_blueprint.route("/<slug>", methods=['GET', 'POST'])
@login_required
def election(slug):
    election = Election.query.filter_by(slug=slug).one_or_none()

    if election == None:
        abort(404, 'No such election.')
    if election.public == False and not current_user.is_wizard:
        abort(403, 'No access.')

    candidates = Candidate.query.filter_by(election_id=election.id).all()
    candidate_ids = {c.id for c in candidates}

    existing_vote = VoteReceipt.query.filter(
        VoteReceipt.user_id == current_user.id,
        VoteReceipt.election_id == election.id,
    ).first()

    no_vote = None
    if existing_vote:
        no_vote = "You already voted in this election! Thank you!"
    if election.ends_at < datetime.now():
        no_vote = "This election has already ended."
    if current_user.id > election.minimum_user_id:
        no_vote = "Your account is too new to vote in this election.  (Maybe you are not logged in with the same account that you normally use?  You can <a href=\"https://auth.rebble.io/account/\">log out and try again</a>, if so.)"

    if request.method == 'GET':
        return render_template('vote.html', election=election, candidates=random.sample(candidates, k=len(candidates)), no_vote=no_vote)

    if no_vote:
        flash(no_vote, "voting")
        return redirect(url_for('voting.elections'))

    try:
        if request.form['vote'] == '':
            ranking = []
        else:
            ranking = [int(c) for c in request.form['vote'].split(',')]
    except:
        flash("Hey, somehow your vote didn't get included in the HTTP POST!", "voting");
        return redirect(url_for('voting.election', slug=slug))

    for c in ranking:
        if c not in candidate_ids:
            flash("Invalid candidate in submission.", "voting")
            return redirect(url_for('voting.election', slug=slug))
    
    if len(ranking) < 3:
        flash("You must rank at least 3 candidates.", "voting")
        return redirect(url_for('voting.election', slug=slug))

    db.session.add(VoteReceipt(user_id=current_user.id, election_id=election.id, voted_at=datetime.now()))
    vote = Vote(election_id=election.id, vote=ranking)
    db.session.add(vote)
    db.session.commit()

    flash(f"Your vote (ID #{vote.uuid}) has been recorded. Thank you!", "voting")
    return redirect(url_for('voting.elections'))


def init_app(app):
    app.register_blueprint(voting_blueprint, url_prefix='/vote')
