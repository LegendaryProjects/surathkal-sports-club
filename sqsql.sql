CREATE DATABASE IF NOT EXISTS surathkal_sports_club2
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE surathkal_sports_club2;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  email VARCHAR(120) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL
);

-- NEW TABLE: Resolves string duplication and update anomalies
CREATE TABLE IF NOT EXISTS sports (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(60) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS teams (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  sport_id INT NOT NULL,
  CONSTRAINT fk_team_sport FOREIGN KEY (sport_id)
    REFERENCES sports(id)
    ON DELETE RESTRICT,
  CONSTRAINT uq_team_name_sport UNIQUE (name, sport_id)
);

CREATE TABLE IF NOT EXISTS players (
  id INT AUTO_INCREMENT PRIMARY KEY,
  team_id INT NOT NULL,
  player_name VARCHAR(80) NOT NULL,
  age INT NOT NULL,
  jersey_name VARCHAR(40) NOT NULL,
  jersey_number INT NOT NULL,
  created_by INT NOT NULL,
  CONSTRAINT fk_player_team FOREIGN KEY (team_id)
    REFERENCES teams(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_player_creator FOREIGN KEY (created_by)
    REFERENCES users(id)
    ON DELETE CASCADE,
  CONSTRAINT uq_team_jersey_number UNIQUE (team_id, jersey_number),
  CONSTRAINT uq_team_jersey_name UNIQUE (team_id, jersey_name),
  CONSTRAINT uq_team_player_name UNIQUE (team_id, player_name),
  CHECK (age BETWEEN 5 AND 80),
  CHECK (jersey_number BETWEEN 1 AND 99)
);

-- UPDATED: Added sport_id to link the tournament to a specific sport
CREATE TABLE IF NOT EXISTS tournaments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  sport_id INT NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  created_by INT NOT NULL,
  CONSTRAINT fk_tournament_sport FOREIGN KEY (sport_id)
    REFERENCES sports(id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_tournament_creator FOREIGN KEY (created_by)
    REFERENCES users(id)
    ON DELETE CASCADE,
  CHECK (end_date > start_date)
);

-- UPDATED: Removed the 'sport' column (3NF violation)
CREATE TABLE IF NOT EXISTS tournament_matches (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tournament_id INT NOT NULL,
  team_one_id INT NOT NULL,
  team_two_id INT NOT NULL,
  match_date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  created_by INT NOT NULL,
  CONSTRAINT fk_match_tournament FOREIGN KEY (tournament_id)
    REFERENCES tournaments(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_match_team_one FOREIGN KEY (team_one_id)
    REFERENCES teams(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_match_team_two FOREIGN KEY (team_two_id)
    REFERENCES teams(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_match_creator FOREIGN KEY (created_by)
    REFERENCES users(id)
    ON DELETE CASCADE,
  CONSTRAINT uq_tournament_match_slot UNIQUE (
    tournament_id,
    team_one_id,
    team_two_id,
    match_date,
    start_time
  ),
  CHECK (end_time > start_time),
  CHECK (team_one_id != team_two_id) -- Ensures a team doesn't play itself
);