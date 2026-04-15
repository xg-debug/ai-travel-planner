-- AI Travel Planner - MySQL 8.0 Schema
-- Apply with: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS ai_travel_planner
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE ai_travel_planner;

CREATE TABLE IF NOT EXISTS users (
  id CHAR(36) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(120) NOT NULL,
  avatar_url VARCHAR(500) NULL,
  email_verified TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_login_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS trips (
  id CHAR(36) NOT NULL,
  user_id CHAR(36) NOT NULL,
  destination VARCHAR(255) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  travelers INT NOT NULL DEFAULT 1,
  interests_json JSON NOT NULL,
  budget_total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  budget_currency VARCHAR(10) NOT NULL DEFAULT 'CNY',
  plan_text LONGTEXT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'planned',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_trips_user_id (user_id),
  KEY idx_trips_destination (destination),
  CONSTRAINT fk_trips_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS trip_days (
  id CHAR(36) NOT NULL,
  trip_id CHAR(36) NOT NULL,
  day_index INT NOT NULL,
  day_date DATE NOT NULL,
  notes TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_trip_days_trip_day (trip_id, day_index),
  KEY idx_trip_days_trip_id (trip_id),
  CONSTRAINT fk_trip_days_trip
    FOREIGN KEY (trip_id) REFERENCES trips(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS trip_activities (
  id CHAR(36) NOT NULL,
  trip_day_id CHAR(36) NOT NULL,
  time VARCHAR(20) NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NULL,
  location VARCHAR(255) NOT NULL,
  type VARCHAR(50) NOT NULL,
  duration INT NOT NULL DEFAULT 60,
  cost DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  notes TEXT NULL,
  lat DECIMAL(10,7) NULL,
  lng DECIMAL(10,7) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_trip_activities_trip_day_id (trip_day_id),
  CONSTRAINT fk_trip_activities_trip_day
    FOREIGN KEY (trip_day_id) REFERENCES trip_days(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS trip_plans (
  id CHAR(36) NOT NULL,
  user_id CHAR(36) NOT NULL,
  destination VARCHAR(255) NOT NULL,
  start_date VARCHAR(20) NOT NULL,
  end_date VARCHAR(20) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_trip_plans_user_id (user_id),
  KEY idx_trip_plans_destination (destination),
  CONSTRAINT fk_trip_plans_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id CHAR(36) NOT NULL,
  user_id CHAR(36) NOT NULL,
  token_hash CHAR(64) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_password_reset_tokens_token_hash (token_hash),
  KEY idx_password_reset_tokens_user_id (user_id),
  KEY idx_password_reset_tokens_expires_at (expires_at),
  CONSTRAINT fk_password_reset_tokens_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
