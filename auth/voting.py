from flask import Blueprint, request, abort, redirect, render_template, flash, url_for, current_app
from flask_login import login_required, current_user
from datetime import datetime

from auth.models import db, Election, Candidate, Vote

voting_blueprint = Blueprint("voting", __name__)

@voting_blueprint.route("/", methods=['GET'])
@login_required
def elections():
    elections = Election.query.filter(Election.public!=current_user.is_wizard, Election.ends_at>=datetime.now())
    return render_template('elections.html', elections=elections)

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

    existing_vote = Vote.query.filter(
        Vote.user_id == current_user.id,
        Vote.candidate_id.in_(candidate_ids)
    ).first()

    if existing_vote:
        flash("You already voted in this election! Thank you!", "error")
        return redirect(url_for('voting.elections'))

    if request.method == 'GET':
        return render_template('vote.html', election=election, candidates=candidates)

    rankings = {}
    for key, value in request.form.items():
        if not key.startswith('candidate_'):
            continue
        if value == '':
            continue
        candidate_id = key[len('candidate_'):]
        try:
            int(candidate_id)
        except ValueError:
            flash("Candidate IDs must be integers.", "error")
            return redirect(url_for('voting.election', slug=slug))
        if int(candidate_id) not in candidate_ids:
            flash("Invalid candidate in submission.", "error")
            return redirect(url_for('voting.election', slug=slug))
        try:
            rank = int(value)
        except ValueError:
            flash("Ranks must be integers.", "error")
            return redirect(url_for('voting.election', slug=slug))
        if rank == 0:
            continue
        rankings[candidate_id] = rank

    ranked_values = list(rankings.values())

    if len(ranked_values) < 3:
        flash("You must rank at least 3 candidates.", "error")
        return redirect(url_for('voting.election', slug=slug))

    sorted_ranks = sorted(ranked_values)
    expected = list(range(1, len(sorted_ranks) + 1))
    current_app.logger.info(expected)
    if sorted_ranks != expected:
        flash(
            "Ranks must start at 1 and increase by 1 with no gaps "
            f"(e.g. 1, 2, 3…). You submitted: {sorted_ranks}",
            "error"
        )
        return redirect(url_for('voting.election', slug=slug))

    for candidate_id, rank in rankings.items():
        vote = Vote(candidate_id=int(candidate_id), rank=rank, user_id=current_user.id)
        db.session.add(vote)
    db.session.commit()

    flash("Your vote has been recorded. Thank you!", "success")
    return redirect(url_for('voting.elections'))



def init_app(app):
    app.register_blueprint(voting_blueprint, url_prefix='/vote')
