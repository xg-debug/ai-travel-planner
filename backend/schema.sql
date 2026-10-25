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

CREATE TABLE IF NOT EXISTS trip_plans (
  id CHAR(36) NOT NULL,
  user_id CHAR(36) NOT NULL,
  destination VARCHAR(255) NOT NULL,
  start_date VARCHAR(20) NOT NULL,
  end_date VARCHAR(20) NOT NULL,
  travelers INT NOT NULL DEFAULT 1,
  interests_json JSON NOT NULL,
  budget_total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  budget_currency VARCHAR(10) NOT NULL DEFAULT 'CNY',
  status VARCHAR(20) NOT NULL DEFAULT 'planned',
  cover_image_url VARCHAR(500) NULL,
  payload_json LONGTEXT NOT NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_trip_plans_user_id (user_id),
  KEY idx_trip_plans_destination (destination),
  KEY idx_trip_plans_status (status),
  CONSTRAINT fk_trip_plans_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS planning_jobs (
  id CHAR(36) NOT NULL,
  user_id CHAR(36) NULL,
  guest_token_hash CHAR(64) NULL,
  request_json JSON NOT NULL,
  checkpoint_json JSON NULL,
  result_json JSON NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'queued',
  step VARCHAR(60) NOT NULL DEFAULT 'request_analysis',
  message VARCHAR(255) NOT NULL DEFAULT '规划任务已排队',
  progress INT NOT NULL DEFAULT 0,
  attempt INT NOT NULL DEFAULT 0,
  lease_until DATETIME NULL,
  error TEXT NULL,
  error_code VARCHAR(80) NULL,
  retryable TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_planning_jobs_status_lease (status, lease_until),
  KEY ix_planning_jobs_owner_created (user_id, created_at),
  CONSTRAINT fk_planning_jobs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_runs (
  id CHAR(36) NOT NULL,
  job_id CHAR(36) NULL,
  user_id CHAR(36) NULL,
  source VARCHAR(20) NOT NULL,
  attempt INT NOT NULL DEFAULT 1,
  city VARCHAR(100) NOT NULL DEFAULT '',
  days INT NOT NULL DEFAULT 1,
  status VARCHAR(20) NOT NULL DEFAULT 'running',
  error_code VARCHAR(80) NULL,
  result_summary JSON NULL,
  model_calls INT NOT NULL DEFAULT 0,
  tool_calls INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  duration_ms INT NULL,
  PRIMARY KEY (id),
  KEY ix_agent_runs_job_attempt (job_id, attempt),
  KEY ix_agent_runs_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_trace_events (
  id INT NOT NULL AUTO_INCREMENT,
  run_id CHAR(36) NOT NULL,
  kind VARCHAR(24) NOT NULL,
  name VARCHAR(120) NOT NULL,
  status VARCHAR(20) NOT NULL,
  provider VARCHAR(50) NULL,
  model VARCHAR(120) NULL,
  endpoint VARCHAR(120) NULL,
  duration_ms INT NULL,
  input_summary JSON NULL,
  output_summary JSON NULL,
  error_code VARCHAR(80) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_agent_trace_events_run_id_id (run_id, id),
  CONSTRAINT fk_agent_trace_events_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
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
