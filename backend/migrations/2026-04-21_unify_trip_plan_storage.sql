USE ai_travel_planner;

ALTER TABLE trip_plans
  ADD COLUMN travelers INT NOT NULL DEFAULT 1 AFTER end_date,
  ADD COLUMN interests_json JSON NOT NULL AFTER travelers,
  ADD COLUMN budget_total DECIMAL(12,2) NOT NULL DEFAULT 0.00 AFTER interests_json,
  ADD COLUMN budget_currency VARCHAR(10) NOT NULL DEFAULT 'CNY' AFTER budget_total,
  ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'planned' AFTER budget_currency,
  ADD COLUMN cover_image_url VARCHAR(500) NULL AFTER status;

ALTER TABLE trip_plans
  ADD KEY idx_trip_plans_status (status);

UPDATE trip_plans
SET
  travelers = COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload_json, '$.travelers')), 1),
  interests_json = COALESCE(JSON_EXTRACT(payload_json, '$.interests'), JSON_ARRAY()),
  budget_total = COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload_json, '$.budget.total')), 0),
  budget_currency = COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload_json, '$.budget.currency')), 'CNY'),
  status = COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload_json, '$.status')), 'planned'),
  cover_image_url = COALESCE(
    JSON_UNQUOTE(JSON_EXTRACT(payload_json, '$.recommendations[0].image')),
    JSON_UNQUOTE(JSON_EXTRACT(payload_json, '$.recommendations[0].image_url')),
    cover_image_url
  );

DROP TABLE IF EXISTS trip_activities;
DROP TABLE IF EXISTS trip_days;
DROP TABLE IF EXISTS trips;
