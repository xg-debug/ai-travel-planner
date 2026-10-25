-- Apply to an existing MySQL installation. New installations use schema.sql.
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
