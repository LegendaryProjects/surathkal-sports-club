# Surathkal Sports Club DBMS Project

This Flask web application manages:

- Organizer accounts
- Team creation (team name + game name)
- Player management inside each team
- Tournament event creation with date ranges
- Match scheduling between existing teams
- Jersey names and jersey numbers per team

The backend now uses MySQL with relational constraints.

## Relational Rules Implemented

- A jersey number must be unique within a team.
- A jersey name must be unique within a team.
- A player name cannot repeat inside the same team.
- Match teams must belong to the same game.
- Team match time cannot overlap for the same game.

## Technology Stack

- Python + Flask
- Flask-SQLAlchemy
- MySQL + PyMySQL
- Flask-Session
- Bootstrap 5 + custom CSS

## Project Setup (Windows PowerShell)

1. Open the project:

```powershell
cd C:\VSCodeProjects\Python\dbms-project
```

2. Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. Set MySQL environment variables (edit values as needed):

```powershell
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="your_mysql_password"
$env:MYSQL_DB="surathkal_sports_club"
$env:SECRET_KEY="replace-with-a-secure-random-string"
```

4. Ensure MySQL server is running.

5. Start the app:

```powershell
python app.py
```

6. Open:

```text
http://127.0.0.1:5000
```

## Database Schema

See mysql_schema.sql for complete DDL.

## Notes

- The app auto-creates the configured database if it does not exist.
- This version removes all CS50 dependencies and SQLite-specific logic.



