-- Existing MySQL installations. New databases use schema.sql.
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
