# Database Schema (MySQL)

## Overview

当前项目的数据库主设计已经统一为：

1. `users`
2. `trip_plans`
3. `password_reset_tokens`

基准初始化脚本位于 [backend/schema.sql](/Users/xugang/workspace/ai-travel-planner/backend/schema.sql)。  
结构化 JSON 描述位于 [docs/schema.json](/Users/xugang/workspace/ai-travel-planner/docs/schema.json)。

SQLAlchemy URL 格式：

`mysql+pymysql://<user>:<password>@<host>:3306/ai_travel_planner?charset=utf8mb4`

## Current Tables

### 1. `users`

用途：

1. 用户账号身份与基础资料
2. 作为行程和密码找回记录的根表

关键字段：

1. `id`
2. `email`
3. `password_hash`
4. `name`
5. `avatar_url`
6. `email_verified`
7. `created_at`
8. `updated_at`
9. `last_login_at`

约束：

1. `email` 唯一
2. `id` 主键

### 2. `trip_plans`

用途：

1. 当前唯一的行程主存储表
2. 采用“结构化摘要字段 + 完整 JSON 快照”模式

关键字段：

1. `id`
2. `user_id`
3. `destination`
4. `start_date`
5. `end_date`
6. `travelers`
7. `interests_json`
8. `budget_total`
9. `budget_currency`
10. `status`
11. `cover_image_url`
12. `payload_json`
13. `created_at`
14. `updated_at`

说明：

1. `payload_json` 保存完整 itinerary 快照，前端保存和回显直接依赖它。
2. `destination`、`status`、`budget_total`、`updated_at` 等字段用于列表过滤和排序。
3. `cover_image_url` 只应保存短的、可持久化的 `http/https` 图片 URL，不应保存 `data:image/...` 内联占位图。

### 3. `password_reset_tokens`

用途：

1. 支持忘记密码和重置密码流程

关键字段：

1. `id`
2. `user_id`
3. `token_hash`
4. `expires_at`
5. `used_at`
6. `created_at`

约束：

1. `token_hash` 唯一
2. 级联依赖 `users`

## Retain / Remove Recommendation

### 应保留的表

#### `users`

必须保留。它是认证、授权和数据归属的核心根表。

#### `trip_plans`

必须保留。它已经是当前项目真实在线链路的唯一行程主存储表，后端接口、前端历史记录、保存和更新逻辑都依赖它。

#### `password_reset_tokens`

建议保留。它是用户系统的一部分，且已经进入现有认证流程。

### 应移除的表

#### `trips`

应移除。它代表旧的标准化行程头表，但当前代码不再读写它，继续保留只会制造双轨存储认知负担。

#### `trip_days`

应移除。它依附于旧的标准化行程设计，当前没有在线写入和查询链路。

#### `trip_activities`

应移除。它同样属于旧设计，和 `trip_plans.payload_json` 的当前主存储模型冲突。

#### `user_preferences`

应移除。当前仓库没有对应 ORM、接口和实际表定义，只存在于旧文档里。

#### `feedbacks`

应移除。当前仓库没有实际表定义、在线接口或业务链路，只存在于旧文档里。

## Why Single-Table Trip Storage Is Better Now

当前阶段保留 `trip_plans` 单表主存储，是更合理的选择：

1. 当前业务是“整份行程生成、整份行程展示、整份行程保存”，不是复杂的事务型多表编辑。
2. 单一真相源能避免多表写入一致性问题。
3. 前端当前就是以完整 payload 为中心工作，和 `payload_json` 模型天然匹配。
4. 通过补充结构化摘要字段，已经能满足列表页、筛选、排序和基础统计需求。

## Recommended Next Tables

如果后续继续往生产级演进，最值得新增的不是把 `trip_days` / `trip_activities` 捞回来，而是新增 agent 运行日志表：

1. `trip_generation_jobs`
2. `trip_generation_tasks`
3. `trip_generation_events`

它们更有助于：

1. 排查 planner / worker / reflection 链路问题
2. 统计耗时、失败率、fallback 频次
3. 支撑服务器部署后的可观测性

## Migration Note

如果数据库还是旧版本，请执行已提供的迁移脚本：

[backend/migrations/2026-04-21_unify_trip_plan_storage.sql](/Users/xugang/workspace/ai-travel-planner/backend/migrations/2026-04-21_unify_trip_plan_storage.sql)

该脚本会：

1. 扩展 `trip_plans`
2. 回填结构化字段
3. 删除 `trips / trip_days / trip_activities`
