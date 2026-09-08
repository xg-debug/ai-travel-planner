# AI Travel Planner 安装部署与使用文档

## 环境要求

| 组件      | 版本要求        | 说明                        |
| ------- | ----------- | ------------------------- |
| Python  | ≥ 3.12      | 后端运行环境                    |
| Node.js | ≥ 18（推荐 24） | 小程序构建                     |
| MySQL   | 8.0+        | 主数据库，需启用 utf8mb4          |
| Redis   | 6.0+        | 缓存（可选，无 Redis 时自动降级为内存缓存） |
| npm     | 最新稳定版       | 包管理器                      |

***

## 项目结构

```
ai-travel-planner/
├── backend/            # FastAPI 后端（Python）
├── miniapp/            # 微信小程序（uni-app）
├── doc/                # 设计文档与部署文档
└── README.md
```

***

# 第一部分：安装部署

## 一、数据库初始化

### 1.1 安装 MySQL 8.0

macOS：

```bash
brew install mysql@8.0
brew services start mysql@8.0
```

Linux (Ubuntu/Debian)：

```bash
sudo apt install mysql-server-8.0
sudo systemctl start mysql
```

### 1.2 创建数据库

```bash
mysql -u root -p < backend/schema.sql
```

以上命令会创建 `ai_travel_planner` 数据库及三张核心表：

| 表名                      | 说明     |
| ----------------------- | ------ |
| `users`                 | 用户账户   |
| `trip_plans`            | 行程计划   |
| `password_reset_tokens` | 密码重置令牌 |

> 启动时后端还会通过 SQLAlchemy 自动创建 `user_roles`、`runtime_settings`、`user_activity_events` 表。

### 1.3 运行迁移（可选）

```bash
mysql -u root -p ai_travel_planner < backend/migrations/2026-04-21_unify_trip_plan_storage.sql
```

***

## 二、后端部署

### 2.1 创建虚拟环境

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### 2.2 安装依赖

```bash
pip install -r requirements.txt
```

### 2.3 配置环境变量

项目已有 `.env` 文件模板，按需修改：

```bash
cp .env .env.production
```

**必须配置的变量：**

```env
# 数据库（修改为你的实际连接信息）
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/ai_travel_planner?charset=utf8mb4

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM — 至少配置一个提供商的 API Key
DEEPSEEK_API_KEY=sk-xxxxxxxx        # DeepSeek（推荐，国内可直接访问）
OPENAI_API_KEY=sk-xxxxxxxx          # OpenAI
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx   # Anthropic
GOOGLE_API_KEY=xxxxxxxx             # Google Gemini

# 默认使用的 LLM
DEFAULT_LLM_PROVIDER=deepseek
DEFAULT_LLM_MODEL=deepseek-v4-flash

# 地图服务（POI、天气等使用高德官方 MCP Streamable HTTP）
MAP_PROVIDER=amap_mcp
AMAP_MCP_URL=https://mcp.amap.com/mcp # 高德官方 MCP HTTP 入口
AMAP_MCP_API_KEY=xxxxxxxx           # 高德 MCP Key，兼容原 AMAP_API_KEY
AMAP_ROAD_GEOMETRY_ENABLED=false   # 可选：允许使用高德 Web 服务补充真实道路折线

# 备用地图服务
AMAP_API_KEY=xxxxxxxx               # 原高德 Key，兼容用于 MCP 鉴权
TENCENT_MAP_API_KEY=xxxxxxxx        # 腾讯地图，仅 MAP_PROVIDER=tencent 时使用

# 安全
SECRET_KEY=更换为随机字符串

# Unsplash 图片（可选）
UNSPLASH_ACCESS_KEY=xxxxxxxx
UNSPLASH_SECRET_KEY=xxxxxxxx
```

**完整环境变量参考：**

| 变量                                        | 默认值                             | 说明                  |
| ----------------------------------------- | ------------------------------- | ------------------- |
| `DEBUG`                                   | `false`                         | 调试模式                |
| `HOST`                                    | `0.0.0.0`                       | 监听地址                |
| `PORT`                                    | `8000`                          | 监听端口                |
| `CORS_ORIGINS`                            | `localhost:3000,localhost:5173` | 允许跨域的来源             |
| `DATABASE_URL`                            | —                               | MySQL 连接串           |
| `REDIS_URL`                               | `redis://localhost:6379/0`      | Redis 连接串           |
| `SECRET_KEY`                              | —                               | JWT 签名密钥            |
| `ACCESS_TOKEN_EXPIRE_MINUTES`             | `720`                           | 普通登录 Token 有效期（分钟）  |
| `ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER_ME` | `43200`                         | 记住我 Token 有效期（30 天） |
| `DEFAULT_LLM_PROVIDER`                    | —                               | 默认 LLM 提供商          |
| `DEFAULT_LLM_MODEL`                       | —                               | 默认模型名               |
| `LLM_TEMPERATURE`                         | `0.7`                           | LLM 温度参数            |
| `LLM_MAX_TOKENS`                          | `4000`                          | LLM 最大输出 Token      |
| `LLM_REQUEST_TIMEOUT_SECONDS`             | `45`                            | LLM 请求超时（秒）         |
| `LLM_MAX_RETRIES`                         | `1`                             | LLM 调用最大重试次数        |
| `MAP_PROVIDER` | `amap_mcp` | 默认高德 MCP，兼容旧 amap / amap_mcp_sse；也可手动选择 tencent |
| `AMAP_MCP_URL` | `https://mcp.amap.com/mcp` | 高德官方 Streamable HTTP 地址 |
| `AMAP_MCP_API_KEY`                        | —                               | 高德 MCP 鉴权 Key，如服务 URL 已带 Key 可不填 |
| `AMAP_MCP_HEADERS`                        | —                               | 额外请求头 JSON，例如 `{"x-api-key":"..."}` |
| `AMAP_API_KEY` | — | 兼容已有高德 Key，调用仍通过 MCP |
| `TENCENT_MAP_API_KEY`                     | —                               | 腾讯地图 Key            |
| `WEATHER_API_KEY`                         | —                               | 天气服务 Key            |
| `MAX_TRIP_DAYS`                           | `7`                             | 单次行程最大天数            |
| `MAX_ACTIVITIES_PER_DAY`                  | `6`                             | 每天最多活动数             |
| `CACHE_TTL`                               | `3600`                          | 缓存过期时间（秒）           |
| `RATE_LIMIT_PER_MINUTE`                   | `60`                            | 每分钟请求限制             |
| `LOG_LEVEL`                               | `INFO`                          | 日志级别                |
| `LOG_FILE`                                | —                               | 日志文件路径（留空仅输出到控制台）   |

### 2.4 启动后端

开发模式（热重载）：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

生产模式（推荐使用 gunicorn）：

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 2.5 验证

```bash
curl http://localhost:8000/api/trip/health
# 返回: {"status": "healthy"}

# 访问 API 文档
open http://localhost:8000/api/docs
```

***

## 三、小程序部署（uni-app）

### 3.1 安装依赖

```bash
cd miniapp
npm install
```

### 3.2 配置环境变量

```bash
cp .env.example .env.local
```

编辑 `.env.local`：

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

> 生产环境替换为后端实际部署地址。小程序需在微信公众平台将后端域名加入 request 合法域名列表。

### 3.3 配置微信小程序

编辑 `project.config.json`，确认 `appid` 为你的小程序 AppID：

```json
{
  "appid": "wxba6ff8eb7b3969cb"
}
```

> 需要在 [微信公众平台](https://mp.weixin.qq.com) 注册小程序并获取 AppID。

### 3.4 开发与构建

```bash
# 开发模式（编译到微信小程序）
npm run dev:mp-weixin

# 生产构建
npm run build:mp-weixin
```

编译产物在 `dist/dev/mp-weixin`（开发）或 `dist/build/mp-weixin`（生产）。使用**微信开发者工具**导入该目录即可预览/上传。

***

## 四、生产环境检查清单

### 安全

- [ ] 修改 `SECRET_KEY` 为随机字符串（`openssl rand -hex 32`）
- [ ] 所有 API Key 替换为生产密钥，移除占位符值
- [ ] 设置 `DEBUG=false`
- [ ] 配置 `CORS_ORIGINS` 为实际域名
- [ ] 数据库使用强密码，限制来源 IP
- [ ] 小程序服务器域名已配置白名单
- [ ] 配置 HTTPS（通过 Nginx 反向代理或 CDN）

### 性能

- [ ] 确保 Redis 正常运行（`redis-cli ping` 返回 PONG）
- [ ] 根据服务器配置调整 gunicorn worker 数量（建议 `CPU 核数 × 2`）
- [ ] 配置 MySQL 连接池

### 监控

- [ ] 配置 `LOG_FILE` 指定日志文件路径
- [ ] 设置日志轮转（logrotate 或应用内 RotatingFileHandler）
- [ ] 监控 API 健康端点 `/api/trip/health`

***

## 五、故障排除

### 后端启动失败

```bash
# 检查 Python 版本
python3 --version  # 需要 ≥ 3.12

# 检查依赖
pip install -r requirements.txt

# 检查端口占用
lsof -i:8000

# 检查 MySQL 连接
mysql -u root -p -e "SELECT 1"

# 检查 Redis 连接
redis-cli ping
```

### LLM 调用不可用

- 确认至少配置了一个有效的 API Key
- DeepSeek（国内可用，无需代理）
- OpenAI / Anthropic / Google 可能需要代理，确认网络可达
- 检查 `DEFAULT_LLM_PROVIDER` 和 `DEFAULT_LLM_MODEL` 是否匹配

### 小程序编译报错

```bash
# 清除缓存重试
rm -rf node_modules dist
npm install
npm run dev:mp-weixin
```

### 地图不显示

- 确认 `AMAP_API_KEY` 已配置高德 Web 服务 Key
- 小程序需要单独申请高德微信小程序 Key
- 在微信公众平台将地图服务域名加入白名单

### 数据库问题

如果启动时表创建失败，检查 MySQL 用户权限：

```sql
GRANT ALL PRIVILEGES ON ai_travel_planner.* TO 'root'@'127.0.0.1';
FLUSH PRIVILEGES;
```

***

## 六、开发环境一键启动

```bash
# 终端 1 — 后端
cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2 — 小程序
cd miniapp && npm run dev:mp-weixin
```

> 后端启动时会自动创建未存在的数据库表，无需手动执行额外 SQL。

***

# 第二部分：使用指南

## 七、小程序页面导航

小程序包含三个底部 Tab 和若干子页面：

| Tab / 页面 | 路径                         | 说明               |
| -------- | -------------------------- | ---------------- |
| **规划**   | `pages/plan/index`         | 填写旅行需求，发起智能规划    |
| **行程**   | `pages/trips/index`        | 查看所有已保存的行程记录     |
| **我的**   | `pages/profile/index`      | 个人中心、登录、设置       |
| 生成中      | `pages/generating/index`   | AI 生成进度展示        |
| 行程详情     | `pages/trip-detail/index`  | 行程总览（每日安排、地图、预算） |
| 当日安排     | `pages/day-detail/index`   | 单日活动时间线          |
| 地点详情     | `pages/place-detail/index` | 单个景点/活动详情        |
| 路线大图     | `pages/route-map/index`    | 地图路线全屏展示         |
| 登录注册     | `pages/auth/index`         | 邮箱注册/登录          |

***

## 八、智能规划行程

### 8.1 填写需求

打开小程序，默认进入\*\*"规划"\*\* Tab，填写以下信息：

1. **出发城市** — 如"上海"
2. **目的地** — 如"北京"，也可以输入自然语言描述，如"带小朋友去北京玩"
3. **日期范围** — 选择出发日期和返程日期，以及出发/返程时间段
4. **出行人数** — 1-20 人，点击 +/- 调整
5. **人均预算** — 输入整数金额（元）
6. **旅行偏好** — 从标签网格中选择感兴趣的类别：
   - 文化、美食、自然、购物
   - 历史、冒险、休闲、亲子等

> **提示**：目的地支持自然语言输入，系统会自动解析意图。比如输入"周末带娃去北京看故宫"，系统会识别为亲子游、偏好文化历史。

### 8.2 发起规划

填写完毕后，点击底部\*\*"智能规划"**按钮。系统会跳转到**"生成中"\*\*页面，展示：

- **摘要信息** — 目的地、出发城市、天数、人数
- **进度条** — 实时显示 AI 规划的进度百分比
- **步骤状态** — 每个处理阶段的状态（进行中 / 已完成 / 待处理），包括：
  - 意图理解 → 天气查询 → 景点搜索 → 美食搜索
  - 酒店搜索 → 智能评分 → 交通规划 → 行程编排
  - 路线计算 → 信息完善 → 质量审查 → 预算估算 → 生成总结

规划通常需要 **15-60 秒**，具体取决于行程复杂度和 LLM 响应速度。

> **注意**：如果规划失败，页面会显示错误信息和"返回修改需求"按钮，可返回调整后重新规划。

### 8.3 查看行程结果

规划完成后自动跳转到\*\*"行程详情"\*\*页面，包含以下模块：

**行程概览**

- 目的地名称和"X日游"标识
- 总天数/晚数、景点数量、总里程、人均预算

**往返交通**

- 去程和返程的推荐交通方式及预估费用

**路线地图**

- 景点位置标记和路线折线预览
- 点击可进入全屏大图模式，支持按天筛选路线

**天气预报**

- 行程期间的天气预报横向滚动条

**预算分解**

- 按类别（交通、住宿、餐饮、门票等）的预算柱状图

**每日行程**

- 所有天的列表，每天包含活动数量
- 点击某一天进入当日安排详情

**美食与住宿推荐**

- 推荐餐饮和酒店列表，附带评分和理由

***

## 九、查看行程详情

### 9.1 每日时间线

在行程详情页点击某一天，进入\*\*"当日安排"\*\*页面：

- 时间线样式展示当天的所有活动
- 每项活动显示：时间、地点名称、描述、预估费用、标签（门票、时长等）
- 当天住宿推荐（酒店名称、地址、预估价格）

### 9.2 活动/地点详情

点击时间线中的某个活动，进入\*\*"地点详情"\*\*页面：

- 景点活动：类型、名称、描述、时间段、时长、费用、门票信息、备注
- 交通活动：推荐交通方式及理由，列出备选交通方案

### 9.3 路线地图

从行程详情页点击地图区域，进入\*\*"路线大图"\*\*页面：

- 地图上展示所有景点标记和路线连线
- 顶部标签支持按天筛选（全程 / DAY 1 / DAY 2 / ...）
- 点击标记弹出地点卡片，可查看详情
- 点击路线分段可高亮对应段

***

## 十、管理行程记录

### 10.1 保存行程

在行程详情页，系统会自动保存最近生成的行程。如需同步到云端，需要先登录账号。

### 10.2 查看历史行程

切换到\*\*"行程"\*\* Tab，可以看到：

- **最新行程卡片** — 显示最近一次规划，包含目的地、状态、天数、人数、预算
- **历史行程列表** — 所有过往行程，可滚动浏览

行程状态说明：

| 状态  | 含义       |
| --- | -------- |
| 计划中 | 刚生成，尚未出行 |
| 已确认 | 已确定出行    |
| 进行中 | 正在旅行中    |
| 已完成 | 旅行已结束    |

### 10.3 管理操作

- **查看** — 点击行程卡片进入详情
- **新建** — 点击"新建"按钮跳转到规划页面
- **删除** — 在行程详情页可删除不需要的行程

***

## 十一、用户认证

### 11.1 注册账号

1. 进入\*\*"我的"\*\* Tab，点击"登录/注册"
2. 切换到"注册"模式
3. 填写昵称、邮箱、密码
4. 点击"注册"

> 第一个注册的用户自动成为超级管理员。

### 11.2 登录

1. 进入\*\*"我的"\*\* Tab，点击"登录/注册"
2. 输入邮箱和密码
3. 点击"登录"

支持"记住我"选项，勾选后 Token 有效期延长至 30 天。

### 11.3 无需登录也可使用

未登录状态下仍可以：

- 生成行程规划
- 查看当前生成的行程
- 浏览所有功能

登录后可额外：

- 将行程同步保存到云端
- 跨设备查看历史行程
- 管理个人资料

### 11.4 忘记密码

在登录页点击"忘记密码"，输入注册邮箱，系统会发送重置令牌。使用令牌可重设密码。

***

## 十二、个人中心

在\*\*"我的"\*\* Tab 中：

- **个人资料** — 显示姓名和邮箱（已登录时）
- **统计数据** — 总行程数、待出发数、去过的城市数
- **快捷菜单** — 我的行程、创建新规划
- **主题设置** — 切换明暗主题

***

## 十三、API 接口参考

后端提供以下主要接口，小程序通过 `VITE_API_BASE_URL` 配置的地址访问。

### 行程规划

| 方法   | 路径                             | 认证 | 说明                   |
| ---- | ------------------------------ | -- | -------------------- |
| POST | `/api/trip/planning`               | 否  | 同步规划行程，等待完成后返回完整结果   |
| POST | `/api/trip/planning/jobs`          | 否  | 启动异步规划任务，返回 `job_id` |
| GET  | `/api/trip/planning/jobs/{job_id}` | 否  | 轮询异步任务状态与结果          |
| POST | `/api/trip/planning/stream`        | 否  | SSE 流式规划，逐步推送进度和结果   |

### 行程管理

| 方法     | 路径                     | 认证 | 说明         |
| ------ | ---------------------- | -- | ---------- |
| GET    | `/api/trip/plans`      | 是  | 获取已保存的行程列表 |
| POST   | `/api/trip/plans`      | 是  | 保存行程到云端    |
| GET    | `/api/trip/plans/{id}` | 是  | 获取单个行程详情   |
| PUT    | `/api/trip/plans/{id}` | 是  | 更新已保存的行程   |
| DELETE | `/api/trip/plans/{id}` | 是  | 删除行程       |

### 辅助功能

| 方法   | 路径                          | 认证 | 说明                            |
| ---- | --------------------------- | -- | ----------------------------- |
| GET  | `/api/trip/weather`         | 否  | 查询目的地天气（参数：`city`、`days`）     |
| GET  | `/api/trip/pois/search`     | 否  | 搜索景点/POI（参数：`keyword`、`city`） |
| GET  | `/api/trip/recommendations` | 否  | 获取个性化推荐                       |
| POST | `/api/trip/budget/estimate` | 否  | 估算行程预算                        |
| POST | `/api/trip/route/map`       | 否  | 计算多日路线坐标                      |
| GET  | `/api/trip/health`          | 否  | 健康检查                          |

### 认证接口

| 方法   | 路径                          | 认证 | 说明                            |
| ---- | --------------------------- | -- | ----------------------------- |
| POST | `/api/auth/register`        | 否  | 注册（`email`、`password`、`name`） |
| POST | `/api/auth/login`           | 否  | 登录，返回 JWT Token               |
| GET  | `/api/auth/me`              | 是  | 获取当前用户信息                      |
| POST | `/api/auth/forgot-password` | 否  | 发送密码重置邮件                      |
| POST | `/api/auth/reset-password`  | 否  | 重置密码                          |

### 用户接口

| 方法  | 路径              | 认证 | 说明            |
| --- | --------------- | -- | ------------- |
| GET | `/api/users/me` | 是  | 获取当前用户资料      |
| PUT | `/api/users/me` | 是  | 更新个人资料（姓名、头像） |

### 规划请求示例

```json
POST /api/trip/planning
{
  "departureCity": "上海",
  "destination": "北京",
  "startDate": "2026-07-15",
  "endDate": "2026-07-17",
  "departureTime": "08:00",
  "returnArrivalTime": "20:00",
  "days": 3,
  "travelers": 4,
  "interests": ["classic", "history"],
  "budgetAmount": 12000,
  "accommodationPreference": "mid-range",
  "additionalRequirements": "带小朋友去玩，喜欢历史文化"
}
```
