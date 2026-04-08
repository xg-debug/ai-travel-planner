# Database Schema (MySQL)

## Overview

The project now uses **MySQL 8.0** as the default relational database.

- SQLAlchemy URL format:
`mysql+pymysql://<user>:<password>@<host>:3306/ai_travel_planner?charset=utf8mb4`
- Initialization script: [`backend/schema.sql`](/Users/xugang/workspace/ai-travel-planner/backend/schema.sql)

## Core Tables

### 1. `users`
- Stores account identity and profile fields.
- Unique key on `email`.

### 2. `user_preferences`
- One-to-one with `users` by `user_id`.
- Stores theme/language/currency plus JSON settings (`notifications_json`, `travel_style_json`).

### 3. `trips`
- Stores trip header metadata (destination, dates, travelers, budget summary, status).
- Foreign key to `users`.

### 4. `trip_days`
- Stores day-level schedule records.
- Unique constraint on `(trip_id, day_index)`.

### 5. `trip_activities`
- Stores activity-level itinerary items under `trip_days`.
- Includes optional coordinates (`lat`, `lng`).

### 6. `feedbacks`
- Stores user feedback and ratings.
- Indexed by `category` and `created_at`.

## Migrations

Recommended production approach:
1. Manage schema with Alembic for incremental changes.
2. Keep `backend/schema.sql` as bootstrap script for fresh environments.
