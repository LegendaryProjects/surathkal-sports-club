import os
from datetime import datetime
from urllib.parse import quote_plus

import pymysql
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, func, or_, text
from werkzeug.security import check_password_hash, generate_password_hash

from extension import login_required

app = Flask(__name__)


def get_mysql_config():
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DB", "surathkal_sports_club"),
    }


def ensure_database_exists(config):
    connection = pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config['database']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


MYSQL_CONFIG = get_mysql_config()
ensure_database_exists(MYSQL_CONFIG)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{MYSQL_CONFIG['user']}:{quote_plus(MYSQL_CONFIG['password'])}"
    f"@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "surathkal-sports-club-dev")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(app.root_path, "flask_session")
app.config["SESSION_USE_SIGNER"] = True

db = SQLAlchemy(app)
Session(app)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    players_added = db.relationship(
        "Player", back_populates="creator", cascade="all, delete-orphan"
    )
    tournaments_created = db.relationship(
        "Tournament", back_populates="creator", cascade="all, delete-orphan"
    )
    matches_created = db.relationship(
        "TournamentMatch", back_populates="creator", cascade="all, delete-orphan"
    )


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sport = db.Column(db.String(60), nullable=False)
    players = db.relationship(
        "Player", back_populates="team", cascade="all, delete-orphan"
    )
    __table_args__ = (
        UniqueConstraint("name", "sport", name="uq_team_name_sport"),
    )


class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    player_name = db.Column(db.String(80), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    jersey_name = db.Column(db.String(40), nullable=False)
    jersey_number = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    team = db.relationship("Team", back_populates="players")
    creator = db.relationship("User", back_populates="players_added")

    __table_args__ = (
        UniqueConstraint("team_id", "jersey_number", name="uq_team_jersey_number"),
        UniqueConstraint("team_id", "jersey_name", name="uq_team_jersey_name"),
        UniqueConstraint("team_id", "player_name", name="uq_team_player_name"),
    )


class Tournament(db.Model):
    __tablename__ = "tournaments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    creator = db.relationship("User", back_populates="tournaments_created")
    matches = db.relationship(
        "TournamentMatch", back_populates="tournament", cascade="all, delete-orphan"
    )


class TournamentMatch(db.Model):
    __tablename__ = "tournament_matches"

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id"), nullable=False)
    sport = db.Column(db.String(60), nullable=False)
    team_one_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    team_two_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    match_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    tournament = db.relationship("Tournament", back_populates="matches")
    team_one = db.relationship("Team", foreign_keys=[team_one_id])
    team_two = db.relationship("Team", foreign_keys=[team_two_id])
    creator = db.relationship("User", back_populates="matches_created")

    __table_args__ = (
        UniqueConstraint(
            "tournament_id",
            "team_one_id",
            "team_two_id",
            "match_date",
            "start_time",
            name="uq_tournament_match_slot",
        ),
    )


def parse_date(date_value):
    try:
        return datetime.strptime(date_value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_time(time_value):
    try:
        return datetime.strptime(time_value, "%H:%M").time()
    except (ValueError, TypeError):
        return None


def run_schema_migrations():
    user_age_column = db.session.execute(text("SHOW COLUMNS FROM users LIKE 'age'"))
    if user_age_column.first():
        db.session.execute(text("ALTER TABLE users DROP COLUMN age"))

    players_table_exists = db.session.execute(text("SHOW TABLES LIKE 'players'"))
    if players_table_exists.first():
        player_age_column = db.session.execute(text("SHOW COLUMNS FROM players LIKE 'age'"))
        if not player_age_column.first():
            db.session.execute(
                text("ALTER TABLE players ADD COLUMN age INT NOT NULL DEFAULT 18 AFTER player_name")
            )

    db.session.commit()


def remove_demo_users():
    legacy_table_exists = db.session.execute(
        text("SHOW TABLES LIKE 'player_registrations'")
    ).first()
    if legacy_table_exists:
        db.session.execute(
            text(
                """
                DELETE pr FROM player_registrations pr
                JOIN users u ON u.id = pr.user_id
                WHERE LOWER(u.username) LIKE 'demo_%'
                   OR LOWER(u.username) LIKE 'demo2_%'
                   OR LOWER(u.username) LIKE 'namea_%'
                   OR LOWER(u.username) LIKE 'nameb_%'
                """
            )
        )

    db.session.execute(
        text(
            """
            DELETE p FROM players p
            JOIN users u ON u.id = p.created_by
            WHERE LOWER(u.username) LIKE 'demo_%'
               OR LOWER(u.username) LIKE 'demo2_%'
               OR LOWER(u.username) LIKE 'namea_%'
               OR LOWER(u.username) LIKE 'nameb_%'
            """
        )
    )

    db.session.execute(
        text(
            """
            DELETE FROM users
            WHERE LOWER(username) LIKE 'demo_%'
               OR LOWER(username) LIKE 'demo2_%'
               OR LOWER(username) LIKE 'namea_%'
               OR LOWER(username) LIKE 'nameb_%'
            """
        )
    )
    db.session.commit()


with app.app_context():
    db.create_all()
    run_schema_migrations()
    remove_demo_users()


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


def render_login_page(form_data=None, status_code=200):
    return render_template("login.html", form_data=form_data or {}), status_code


def render_register_page(form_data=None, status_code=200):
    return render_template("register.html", form_data=form_data or {}), status_code


def get_team_counts():
    return dict(
        db.session.query(Player.team_id, func.count(Player.id))
        .group_by(Player.team_id)
        .all()
    )


def render_teams_page(form_data=None, status_code=200):
    teams = Team.query.order_by(Team.sport.asc(), Team.name.asc()).all()
    return (
        render_template(
            "sport_register.html",
            teams=teams,
            team_counts=get_team_counts(),
            form_data=form_data or {},
        ),
        status_code,
    )


def render_team_players_page(team, form_data=None, status_code=200):
    players = Player.query.filter_by(team_id=team.id).order_by(Player.jersey_number.asc()).all()
    return (
        render_template(
            "form.html",
            team=team,
            players=players,
            form_data=form_data or {},
        ),
        status_code,
    )


def render_events_page(form_data=None, status_code=200):
    tournaments = Tournament.query.order_by(Tournament.start_date.desc(), Tournament.name.asc()).all()
    return render_template("events.html", tournaments=tournaments, form_data=form_data or {}), status_code


def render_tournament_detail_page(tournament, form_data=None, status_code=200):
    teams = Team.query.order_by(Team.sport.asc(), Team.name.asc()).all()
    matches = (
        TournamentMatch.query.filter_by(tournament_id=tournament.id)
        .order_by(TournamentMatch.match_date.asc(), TournamentMatch.start_time.asc())
        .all()
    )
    return (
        render_template(
            "event_detail.html",
            tournament=tournament,
            teams=teams,
            matches=matches,
            form_data=form_data or {},
        ),
        status_code,
    )


def get_safe_next_url(candidate, fallback):
    if candidate.startswith("/") and not candidate.startswith("//") and "://" not in candidate:
        return candidate
    return fallback


def render_edit_profile_page(user, form_data=None, status_code=200):
    default_data = {
        "username": user.username or "",
        "email": user.email or "",
        "password": "",
        "confirm_password": "",
    }
    return (
        render_template("edit_profile.html", form_data=form_data or default_data),
        status_code,
    )


def render_edit_team_page(team, form_data=None, status_code=200):
    default_data = {
        "team_name": team.name or "",
        "sport": team.sport or "",
    }
    return (
        render_template("edit_team.html", team=team, form_data=form_data or default_data),
        status_code,
    )


def render_edit_player_page(player, form_data=None, status_code=200):
    teams = Team.query.order_by(Team.sport.asc(), Team.name.asc()).all()
    default_data = {
        "team_id": player.team_id,
        "player_name": player.player_name or "",
        "player_age": str(player.age),
        "jersey_name": player.jersey_name or "",
        "jersey_number": str(player.jersey_number),
        "next_url": "",
    }
    return (
        render_template(
            "edit_player.html",
            player=player,
            teams=teams,
            form_data=form_data or default_data,
        ),
        status_code,
    )


def render_edit_tournament_page(tournament, form_data=None, status_code=200):
    default_data = {
        "tournament_name": tournament.name,
        "start_date": tournament.start_date.strftime("%Y-%m-%d"),
        "end_date": tournament.end_date.strftime("%Y-%m-%d"),
        "next_url": f"/events/{tournament.id}",
    }
    return (
        render_template(
            "edit_tournament.html",
            tournament=tournament,
            form_data=form_data or default_data,
        ),
        status_code,
    )


def render_edit_match_page(match, form_data=None, status_code=200):
    teams = Team.query.order_by(Team.sport.asc(), Team.name.asc()).all()
    default_data = {
        "team_one_id": match.team_one_id,
        "team_two_id": match.team_two_id,
        "match_date": match.match_date.strftime("%Y-%m-%d"),
        "start_time": match.start_time.strftime("%H:%M"),
        "end_time": match.end_time.strftime("%H:%M"),
    }
    return (
        render_template(
            "edit_match.html",
            match=match,
            tournament=match.tournament,
            teams=teams,
            form_data=form_data or default_data,
        ),
        status_code,
    )


@app.route("/")
def main_page():
    teams = Team.query.order_by(Team.sport.asc(), Team.name.asc()).all()
    team_counts = dict(
        db.session.query(Player.team_id, func.count(Player.id))
        .group_by(Player.team_id)
        .all()
    )
    recent_players = (
        Player.query.join(Team)
        .order_by(Player.id.desc())
        .limit(12)
        .all()
    )
    return render_template(
        "main_page.html",
        teams=teams,
        team_counts=team_counts,
        recent_players=recent_players,
        total_teams=len(teams),
        total_players=sum(team_counts.values()),
        total_tournaments=Tournament.query.count(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_login_page()

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    form_data = {"email": email}

    if not email:
        flash("Please provide your email.", "error")
        return render_login_page(form_data=form_data, status_code=400)
    if not password:
        flash("Please provide your password.", "error")
        return render_login_page(form_data=form_data, status_code=400)

    user = User.query.filter(func.lower(User.email) == email).first()
    if not user:
        flash("No account found with this email.", "error")
        return render_login_page(form_data=form_data, status_code=400)
    if not check_password_hash(user.password_hash, password):
        flash("Incorrect password.", "error")
        return render_login_page(form_data=form_data, status_code=400)

    session["id"] = user.id
    flash("Welcome back!", "success")
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_register_page()

    username = request.form.get("username", "").strip()
    email = request.form.get("mail", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    form_data = {
        "username": username,
        "mail": email,
    }

    if not username or not email or not password or not confirm_password:
        flash("All fields are required.", "error")
        return render_register_page(form_data=form_data, status_code=400)

    if password != confirm_password:
        flash("Password and confirm password must match.", "error")
        return render_register_page(form_data=form_data, status_code=400)

    if len(password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return render_register_page(form_data=form_data, status_code=400)

    existing_user = User.query.filter(func.lower(User.username) == username.lower()).first()
    if existing_user:
        flash("Username already exists.", "error")
        return render_register_page(form_data=form_data, status_code=400)

    existing_email = User.query.filter(func.lower(User.email) == email).first()
    if existing_email:
        flash("Email is already registered.", "error")
        return render_register_page(form_data=form_data, status_code=400)

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()

    session["id"] = user.id
    flash("Organizer account created successfully.", "success")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/")


@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = db.session.get(User, session["id"])
    if not user:
        flash("Please login again.", "error")
        session.clear()
        return redirect("/login")

    if request.method == "GET":
        return render_edit_profile_page(user)

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    form_data = {
        "username": username,
        "email": email,
        "password": "",
        "confirm_password": "",
    }

    if not username:
        flash("Name cannot be empty.", "error")
        return render_edit_profile_page(user, form_data=form_data, status_code=400)

    if not email:
        flash("Email cannot be empty.", "error")
        return render_edit_profile_page(user, form_data=form_data, status_code=400)

    existing_user = User.query.filter(
        func.lower(User.username) == username.lower(),
        User.id != user.id,
    ).first()
    if existing_user:
        flash("That organizer name is already in use.", "error")
        return render_edit_profile_page(user, form_data=form_data, status_code=400)

    existing_email = User.query.filter(
        func.lower(User.email) == email,
        User.id != user.id,
    ).first()
    if existing_email:
        flash("That email is already in use.", "error")
        return render_edit_profile_page(user, form_data=form_data, status_code=400)

    if password or confirm_password:
        if password != confirm_password:
            flash("Password and confirm password must match.", "error")
            return render_edit_profile_page(user, form_data=form_data, status_code=400)
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_edit_profile_page(user, form_data=form_data, status_code=400)
        user.password_hash = generate_password_hash(password)

    user.username = username
    user.email = email
    db.session.commit()

    flash("Profile updated successfully.", "success")
    return redirect("/profile")


@app.route("/sport_register")
@login_required
def sport_reg():
    return redirect("/teams")


@app.route("/teams", methods=["GET", "POST"])
@login_required
def teams():
    if request.method == "POST":
        team_name = request.form.get("team_name", "").strip()
        sport = request.form.get("sport", "").strip()
        form_data = {
            "team_name": team_name,
            "sport": sport,
        }

        if not team_name or not sport:
            flash("Please provide both team name and game name.", "error")
            return render_teams_page(form_data=form_data, status_code=400)

        existing_team = Team.query.filter(
            func.lower(Team.name) == team_name.lower(),
            func.lower(Team.sport) == sport.lower(),
        ).first()
        if existing_team:
            flash("This team already exists for that game.", "error")
            return render_teams_page(form_data=form_data, status_code=400)

        team = Team(name=team_name, sport=sport)
        db.session.add(team)
        db.session.commit()
        flash("Team created successfully.", "success")
        return redirect("/teams")

    return render_teams_page()


@app.route("/teams/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
def edit_team(team_id):
    team = db.session.get(Team, team_id)
    if not team:
        flash("Team not found.", "error")
        return redirect("/teams")

    if request.method == "GET":
        return render_edit_team_page(team)

    team_name = request.form.get("team_name", "").strip()
    sport = request.form.get("sport", "").strip()
    form_data = {
        "team_name": team_name,
        "sport": sport,
    }

    if not team_name or not sport:
        flash("Please provide both team name and game name.", "error")
        return render_edit_team_page(team, form_data=form_data, status_code=400)

    existing_team = Team.query.filter(
        func.lower(Team.name) == team_name.lower(),
        func.lower(Team.sport) == sport.lower(),
        Team.id != team.id,
    ).first()
    if existing_team:
        flash("Another team with the same name and game already exists.", "error")
        return render_edit_team_page(team, form_data=form_data, status_code=400)

    team.name = team_name
    team.sport = sport
    db.session.commit()

    flash("Team updated successfully.", "success")
    return redirect("/teams")


@app.route("/teams/<int:team_id>/players", methods=["GET", "POST"])
@login_required
def team_players(team_id):
    team = db.session.get(Team, team_id)
    if not team:
        flash("Team not found.", "error")
        return redirect("/teams")

    if request.method == "GET":
        return render_team_players_page(team)

    player_name = request.form.get("player_name", "").strip()
    player_age_raw = request.form.get("player_age", "").strip()
    jersey_name = request.form.get("jersey_name", "").strip()
    jersey_number_raw = request.form.get("jersey_number", "").strip()
    form_data = {
        "player_name": player_name,
        "player_age": player_age_raw,
        "jersey_name": jersey_name,
        "jersey_number": jersey_number_raw,
    }

    if not player_name:
        flash("Please enter player name.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)
    if not player_age_raw.isdigit():
        flash("Please enter a valid player age.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)
    if not jersey_name:
        flash("Please enter a jersey name.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)
    if not jersey_number_raw.isdigit():
        flash("Jersey number must be a valid number.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)

    player_age = int(player_age_raw)
    if player_age < 5 or player_age > 80:
        flash("Player age must be between 5 and 80.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)

    jersey_number = int(jersey_number_raw)
    if jersey_number < 1 or jersey_number > 99:
        flash("Jersey number must be between 1 and 99.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)

    if len(player_name) > 80:
        flash("Player name must be 80 characters or less.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)
    if len(jersey_name) > 40:
        flash("Jersey name must be 40 characters or less.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)

    player_exists = Player.query.filter(
        Player.team_id == team_id,
        func.lower(Player.player_name) == player_name.lower(),
    ).first()
    if player_exists:
        flash(f"Player '{player_name}' is already added in {team.name}.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)

    jersey_number_taken = Player.query.filter_by(
        team_id=team_id, jersey_number=jersey_number
    ).first()
    if jersey_number_taken:
        flash(f"Jersey number {jersey_number} is already taken in {team.name}.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)

    jersey_name_taken = Player.query.filter(
        Player.team_id == team_id,
        func.lower(Player.jersey_name) == jersey_name.lower(),
    ).first()
    if jersey_name_taken:
        flash(f"Jersey name '{jersey_name}' is already taken in {team.name}.", "error")
        return render_team_players_page(team, form_data=form_data, status_code=400)

    player = Player(
        team_id=team_id,
        player_name=player_name,
        age=player_age,
        jersey_name=jersey_name,
        jersey_number=jersey_number,
        created_by=session["id"],
    )
    db.session.add(player)
    db.session.commit()

    flash("Player added successfully.", "success")
    return redirect(f"/teams/{team_id}/players")


@app.route("/teams/<int:team_id>/delete", methods=["POST"])
@login_required
def delete_team(team_id):
    team = db.session.get(Team, team_id)
    if not team:
        flash("Team not found.", "error")
        return redirect("/teams")

    db.session.delete(team)
    db.session.commit()
    flash("Team deleted.", "info")
    return redirect("/teams")


@app.route("/players/<int:player_id>/delete", methods=["POST"])
@login_required
def delete_player(player_id):
    player = db.session.get(Player, player_id)
    if not player:
        flash("Player not found.", "error")
        return redirect("/players")

    team_id = player.team_id
    db.session.delete(player)
    db.session.commit()
    flash("Player removed.", "info")

    next_url = request.form.get("next_url", "").strip()
    return redirect(get_safe_next_url(next_url, f"/teams/{team_id}/players"))


@app.route("/players/<int:player_id>/edit", methods=["GET", "POST"])
@login_required
def edit_player(player_id):
    player = db.session.get(Player, player_id)
    if not player:
        flash("Player not found.", "error")
        return redirect("/players")

    if request.method == "GET":
        next_url = request.args.get("next", "").strip()
        form_data = {
            "team_id": player.team_id,
            "player_name": player.player_name,
            "player_age": str(player.age),
            "jersey_name": player.jersey_name,
            "jersey_number": str(player.jersey_number),
            "next_url": next_url,
        }
        return render_edit_player_page(player, form_data=form_data)

    team_id = request.form.get("team_id", type=int)
    player_name = request.form.get("player_name", "").strip()
    player_age_raw = request.form.get("player_age", "").strip()
    jersey_name = request.form.get("jersey_name", "").strip()
    jersey_number_raw = request.form.get("jersey_number", "").strip()
    next_url = request.form.get("next_url", "").strip()

    form_data = {
        "team_id": team_id,
        "player_name": player_name,
        "player_age": player_age_raw,
        "jersey_name": jersey_name,
        "jersey_number": jersey_number_raw,
        "next_url": next_url,
    }

    if not team_id:
        flash("Please select a team.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)
    if not player_name:
        flash("Please enter player name.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)
    if not player_age_raw.isdigit():
        flash("Please enter a valid player age.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)
    if not jersey_name:
        flash("Please enter a jersey name.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)
    if not jersey_number_raw.isdigit():
        flash("Jersey number must be a valid number.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)

    selected_team = db.session.get(Team, team_id)
    if not selected_team:
        flash("Selected team not found.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)

    player_age = int(player_age_raw)
    if player_age < 5 or player_age > 80:
        flash("Player age must be between 5 and 80.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)

    jersey_number = int(jersey_number_raw)
    if jersey_number < 1 or jersey_number > 99:
        flash("Jersey number must be between 1 and 99.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)

    if len(player_name) > 80:
        flash("Player name must be 80 characters or less.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)
    if len(jersey_name) > 40:
        flash("Jersey name must be 40 characters or less.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)

    player_exists = Player.query.filter(
        Player.team_id == team_id,
        func.lower(Player.player_name) == player_name.lower(),
        Player.id != player.id,
    ).first()
    if player_exists:
        flash(f"Player '{player_name}' already exists in {selected_team.name}.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)

    jersey_number_taken = Player.query.filter_by(
        team_id=team_id,
        jersey_number=jersey_number,
    ).filter(Player.id != player.id).first()
    if jersey_number_taken:
        flash(f"Jersey number {jersey_number} is already taken in {selected_team.name}.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)

    jersey_name_taken = Player.query.filter(
        Player.team_id == team_id,
        func.lower(Player.jersey_name) == jersey_name.lower(),
        Player.id != player.id,
    ).first()
    if jersey_name_taken:
        flash(f"Jersey name '{jersey_name}' is already taken in {selected_team.name}.", "error")
        return render_edit_player_page(player, form_data=form_data, status_code=400)

    player.team_id = team_id
    player.player_name = player_name
    player.age = player_age
    player.jersey_name = jersey_name
    player.jersey_number = jersey_number
    db.session.commit()

    flash("Player updated successfully.", "success")
    return redirect(get_safe_next_url(next_url, "/players"))


@app.route("/change_pass", methods=["GET", "POST"])
@login_required
def change():
    return redirect("/edit_profile")


@app.route("/players")
@login_required
def players():
    player_rows = (
        Player.query
        .join(Team)
        .order_by(Team.sport.asc(), Team.name.asc(), Player.jersey_number.asc())
        .all()
    )
    return render_template("mysports.html", players=player_rows)


@app.route("/events", methods=["GET", "POST"])
@login_required
def events():
    if request.method == "POST":
        tournament_name = request.form.get("tournament_name", "").strip()
        start_date_raw = request.form.get("start_date", "").strip()
        end_date_raw = request.form.get("end_date", "").strip()
        form_data = {
            "tournament_name": tournament_name,
            "start_date": start_date_raw,
            "end_date": end_date_raw,
        }

        if not tournament_name or not start_date_raw or not end_date_raw:
            flash("Please provide tournament name and date range.", "error")
            return render_events_page(form_data=form_data, status_code=400)

        start_date = parse_date(start_date_raw)
        end_date = parse_date(end_date_raw)
        if not start_date or not end_date:
            flash("Please provide valid dates.", "error")
            return render_events_page(form_data=form_data, status_code=400)
        if end_date <= start_date:
            flash("End date must be later than start date.", "error")
            return render_events_page(form_data=form_data, status_code=400)

        existing_tournament = Tournament.query.filter(
            func.lower(Tournament.name) == tournament_name.lower()
        ).first()
        if existing_tournament:
            flash("Tournament name already exists.", "error")
            return render_events_page(form_data=form_data, status_code=400)

        tournament = Tournament(
            name=tournament_name,
            start_date=start_date,
            end_date=end_date,
            created_by=session["id"],
        )
        db.session.add(tournament)
        db.session.commit()

        flash("Tournament created successfully.", "success")
        return redirect(f"/events/{tournament.id}")

    return render_events_page()


@app.route("/events/<int:tournament_id>/edit", methods=["GET", "POST"])
@login_required
def edit_event(tournament_id):
    tournament = db.session.get(Tournament, tournament_id)
    if not tournament:
        flash("Tournament not found.", "error")
        return redirect("/events")

    if request.method == "GET":
        next_url = request.args.get("next", "").strip()
        safe_next_url = get_safe_next_url(next_url, f"/events/{tournament.id}")
        form_data = {
            "tournament_name": tournament.name,
            "start_date": tournament.start_date.strftime("%Y-%m-%d"),
            "end_date": tournament.end_date.strftime("%Y-%m-%d"),
            "next_url": safe_next_url,
        }
        return render_edit_tournament_page(tournament, form_data=form_data)

    tournament_name = request.form.get("tournament_name", "").strip()
    start_date_raw = request.form.get("start_date", "").strip()
    end_date_raw = request.form.get("end_date", "").strip()
    next_url = request.form.get("next_url", "").strip()
    safe_next_url = get_safe_next_url(next_url, f"/events/{tournament.id}")

    form_data = {
        "tournament_name": tournament_name,
        "start_date": start_date_raw,
        "end_date": end_date_raw,
        "next_url": safe_next_url,
    }

    if not tournament_name or not start_date_raw or not end_date_raw:
        flash("Please provide tournament name and date range.", "error")
        return render_edit_tournament_page(tournament, form_data=form_data, status_code=400)

    start_date = parse_date(start_date_raw)
    end_date = parse_date(end_date_raw)
    if not start_date or not end_date:
        flash("Please provide valid dates.", "error")
        return render_edit_tournament_page(tournament, form_data=form_data, status_code=400)
    if end_date <= start_date:
        flash("End date must be later than start date.", "error")
        return render_edit_tournament_page(tournament, form_data=form_data, status_code=400)

    existing_tournament = Tournament.query.filter(
        func.lower(Tournament.name) == tournament_name.lower(),
        Tournament.id != tournament.id,
    ).first()
    if existing_tournament:
        flash("Another tournament with this name already exists.", "error")
        return render_edit_tournament_page(tournament, form_data=form_data, status_code=400)

    out_of_range_match = TournamentMatch.query.filter(
        TournamentMatch.tournament_id == tournament.id,
        or_(
            TournamentMatch.match_date < start_date,
            TournamentMatch.match_date > end_date,
        ),
    ).first()
    if out_of_range_match:
        flash(
            "Existing matches fall outside this new date range. Update or delete those matches first.",
            "error",
        )
        return render_edit_tournament_page(tournament, form_data=form_data, status_code=400)

    tournament.name = tournament_name
    tournament.start_date = start_date
    tournament.end_date = end_date
    db.session.commit()

    flash("Tournament details updated.", "success")
    return redirect(safe_next_url)


@app.route("/events/<int:tournament_id>", methods=["GET", "POST"])
@login_required
def event_details(tournament_id):
    tournament = db.session.get(Tournament, tournament_id)
    if not tournament:
        flash("Tournament not found.", "error")
        return redirect("/events")

    if request.method == "GET":
        return render_tournament_detail_page(tournament)

    team_one_id = request.form.get("team_one_id", type=int)
    team_two_id = request.form.get("team_two_id", type=int)
    match_date_raw = request.form.get("match_date", "").strip()
    start_time_raw = request.form.get("start_time", "").strip()
    end_time_raw = request.form.get("end_time", "").strip()

    form_data = {
        "team_one_id": team_one_id,
        "team_two_id": team_two_id,
        "match_date": match_date_raw,
        "start_time": start_time_raw,
        "end_time": end_time_raw,
    }

    if not team_one_id or not team_two_id or not match_date_raw or not start_time_raw or not end_time_raw:
        flash("Please fill all match details.", "error")
        return render_tournament_detail_page(tournament, form_data=form_data, status_code=400)

    if team_one_id == team_two_id:
        flash("A team cannot play against itself.", "error")
        return render_tournament_detail_page(tournament, form_data=form_data, status_code=400)

    team_one = db.session.get(Team, team_one_id)
    team_two = db.session.get(Team, team_two_id)
    if not team_one or not team_two:
        flash("Please select valid existing teams.", "error")
        return render_tournament_detail_page(tournament, form_data=form_data, status_code=400)

    if team_one.sport.lower() != team_two.sport.lower():
        flash("Only teams from the same game can be matched.", "error")
        return render_tournament_detail_page(tournament, form_data=form_data, status_code=400)

    match_date = parse_date(match_date_raw)
    start_time = parse_time(start_time_raw)
    end_time = parse_time(end_time_raw)
    if not match_date or not start_time or not end_time:
        flash("Please provide valid match date and time range.", "error")
        return render_tournament_detail_page(tournament, form_data=form_data, status_code=400)

    if match_date < tournament.start_date or match_date > tournament.end_date:
        flash("Match date must be within the tournament date range.", "error")
        return render_tournament_detail_page(tournament, form_data=form_data, status_code=400)

    if end_time <= start_time:
        flash("End time must be after start time.", "error")
        return render_tournament_detail_page(tournament, form_data=form_data, status_code=400)

    overlapping_matches = TournamentMatch.query.filter(
        TournamentMatch.match_date == match_date,
        TournamentMatch.sport == team_one.sport,
        or_(
            TournamentMatch.team_one_id.in_([team_one_id, team_two_id]),
            TournamentMatch.team_two_id.in_([team_one_id, team_two_id]),
        ),
    ).all()

    for existing in overlapping_matches:
        if start_time < existing.end_time and end_time > existing.start_time:
            flash(
                "One of the selected teams already has another match in this time range.",
                "error",
            )
            return render_tournament_detail_page(tournament, form_data=form_data, status_code=400)

    match = TournamentMatch(
        tournament_id=tournament.id,
        sport=team_one.sport,
        team_one_id=team_one_id,
        team_two_id=team_two_id,
        match_date=match_date,
        start_time=start_time,
        end_time=end_time,
        created_by=session["id"],
    )
    db.session.add(match)
    db.session.commit()

    flash("Match added to tournament.", "success")
    return redirect(f"/events/{tournament.id}")


@app.route("/events/<int:tournament_id>/delete", methods=["POST"])
@login_required
def delete_event(tournament_id):
    tournament = db.session.get(Tournament, tournament_id)
    if not tournament:
        flash("Tournament not found.", "error")
        return redirect("/events")

    db.session.delete(tournament)
    db.session.commit()
    flash("Tournament deleted.", "info")
    return redirect("/events")


@app.route("/matches/<int:match_id>/delete", methods=["POST"])
@login_required
def delete_match(match_id):
    match = db.session.get(TournamentMatch, match_id)
    if not match:
        flash("Match not found.", "error")
        return redirect("/events")

    tournament_id = match.tournament_id
    db.session.delete(match)
    db.session.commit()
    flash("Match removed from tournament.", "info")
    return redirect(f"/events/{tournament_id}")


@app.route("/matches/<int:match_id>/edit", methods=["GET", "POST"])
@login_required
def edit_match(match_id):
    match = db.session.get(TournamentMatch, match_id)
    if not match:
        flash("Match not found.", "error")
        return redirect("/events")

    tournament = match.tournament
    if not tournament:
        flash("Tournament not found.", "error")
        return redirect("/events")

    if request.method == "GET":
        return render_edit_match_page(match)

    team_one_id = request.form.get("team_one_id", type=int)
    team_two_id = request.form.get("team_two_id", type=int)
    match_date_raw = request.form.get("match_date", "").strip()
    start_time_raw = request.form.get("start_time", "").strip()
    end_time_raw = request.form.get("end_time", "").strip()

    form_data = {
        "team_one_id": team_one_id,
        "team_two_id": team_two_id,
        "match_date": match_date_raw,
        "start_time": start_time_raw,
        "end_time": end_time_raw,
    }

    if not team_one_id or not team_two_id or not match_date_raw or not start_time_raw or not end_time_raw:
        flash("Please fill all match details.", "error")
        return render_edit_match_page(match, form_data=form_data, status_code=400)

    if team_one_id == team_two_id:
        flash("A team cannot play against itself.", "error")
        return render_edit_match_page(match, form_data=form_data, status_code=400)

    team_one = db.session.get(Team, team_one_id)
    team_two = db.session.get(Team, team_two_id)
    if not team_one or not team_two:
        flash("Please select valid existing teams.", "error")
        return render_edit_match_page(match, form_data=form_data, status_code=400)

    if team_one.sport.lower() != team_two.sport.lower():
        flash("Only teams from the same game can be matched.", "error")
        return render_edit_match_page(match, form_data=form_data, status_code=400)

    match_date = parse_date(match_date_raw)
    start_time = parse_time(start_time_raw)
    end_time = parse_time(end_time_raw)
    if not match_date or not start_time or not end_time:
        flash("Please provide valid match date and time range.", "error")
        return render_edit_match_page(match, form_data=form_data, status_code=400)

    if match_date < tournament.start_date or match_date > tournament.end_date:
        flash("Match date must be within the tournament date range.", "error")
        return render_edit_match_page(match, form_data=form_data, status_code=400)

    if end_time <= start_time:
        flash("End time must be after start time.", "error")
        return render_edit_match_page(match, form_data=form_data, status_code=400)

    overlapping_matches = TournamentMatch.query.filter(
        TournamentMatch.id != match.id,
        TournamentMatch.match_date == match_date,
        TournamentMatch.sport == team_one.sport,
        or_(
            TournamentMatch.team_one_id.in_([team_one_id, team_two_id]),
            TournamentMatch.team_two_id.in_([team_one_id, team_two_id]),
        ),
    ).all()

    for existing in overlapping_matches:
        if start_time < existing.end_time and end_time > existing.start_time:
            flash(
                "One of the selected teams already has another match in this time range.",
                "error",
            )
            return render_edit_match_page(match, form_data=form_data, status_code=400)

    match.sport = team_one.sport
    match.team_one_id = team_one_id
    match.team_two_id = team_two_id
    match.match_date = match_date
    match.start_time = start_time
    match.end_time = end_time
    db.session.commit()

    flash("Match updated successfully.", "success")
    return redirect(f"/events/{tournament.id}")


@app.route("/mysp")
@login_required
def mysp_redirect():
    return redirect("/players")


@app.route("/form")
@login_required
def form_redirect():
    return redirect("/teams")


@app.route("/profile")
@login_required
def profile():
    user = db.session.get(User, session["id"])
    if not user:
        session.clear()
        return redirect("/login")

    return render_template(
        "profile.html",
        user=user,
        total_teams=Team.query.count(),
        total_players=Player.query.count(),
        total_tournaments=Tournament.query.count(),
    )


@app.route("/features")
def features():
    return render_template("features.html")


if __name__ == "__main__":
    app.run(debug=True)
