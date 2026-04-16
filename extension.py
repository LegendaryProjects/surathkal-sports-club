import os
from datetime import datetime

import pymysql
from flask import redirect, render_template, session
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, func, text


db = SQLAlchemy()


def load_local_env(app_root_path):
    env_path = os.path.join(app_root_path, ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as file:
        for line in file:
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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


def apology(message, code=400):
    return render_template("apology.html", code=code, message=message), code


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function
