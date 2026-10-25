-- Apply once to existing MySQL installations.
ALTER TABLE trip_plans ADD COLUMN version INT NOT NULL DEFAULT 1;
