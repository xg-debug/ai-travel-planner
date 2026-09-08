<p align="center">
  <img src="assets/readme/hero.png" alt="AI Travel Planner" width="720" />
</p>

<h1 align="center">AI Travel Planner</h1>

<p align="center">面向真实出行的 AI 行程规划系统：从旅行偏好到可执行的多日行程、地点核验和道路路线。</p>

<p align="center">
  <a href="https://github.com/xg-debug/ai-travel-planner/stargazers"><img src="https://img.shields.io/github/stars/xg-debug/ai-travel-planner?style=flat-square" alt="GitHub stars" /></a>
  <a href="https://github.com/xg-debug/ai-travel-planner/issues"><img src="https://img.shields.io/github/issues/xg-debug/ai-travel-planner?style=flat-square" alt="GitHub issues" /></a>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/Vue-3-42b883?style=flat-square&logo=vuedotjs&logoColor=white" alt="Vue 3" />
  <img src="https://img.shields.io/badge/AMap-MCP-00A870?style=flat-square" alt="AMap MCP" />
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#产品能力">产品能力</a> ·
  <a href="#地图与路线">地图与路线</a> ·
  <a href="#项目结构">项目结构</a> ·
  <a href="#接口概览">接口概览</a>
</p>

---

AI Travel Planner 把大模型的行程编排能力和真实地图数据结合起来。用户给出目的地、日期、预算和偏好后，系统会生成多日计划，核验 POI 信息，并把每个地点之间的路线放到真实地图上。Web、小程序和管理后台共用同一套后端与路线数据。

## 界面预览

![系统首页](assets/readme/homepage.png)

![杭州行程的真实道路路线示例](assets/readme/route-map.png)

## 产品能力

| 能力 | 说明 |
| --- | --- |
| AI 多日行程 | 根据出发地、目的地、日期、预算、人数和兴趣生成可调整的每日安排。 |
| 真实 POI 核验 | 对候选景点、酒店和餐饮按 POI ID 补全地址、坐标、营业信息和详情。 |
| 周边餐饮 | 以景点或酒店坐标搜索附近餐饮，让每日安排更顺路。 |
| 多种交通方式 | 支持自动推荐、步行、驾车、骑行与公交；规划、Web 地图和小程序地图复用同一份路线数据。 |
| 真实地图 | Web 使用 Leaflet + OpenStreetMap 底图；小程序使用微信原生地图。没有道路坐标时只显示地点，不用直线伪造路线。 |
| 专属地图导出 | 将多天行程导出到高德专属地图，并提供地点唤端链接。 |
| 可追踪规划过程 | 支持 SSE 和异步任务两种进度通道，显示 Agent 的真实规划状态。 |
| 运行时管理 | 管理后台可维护模型选择、地图服务配置和运行状态。 |

## 地图与路线

项目优先使用高德官方 MCP Server 获取地点、周边搜索、地点详情、天气和路线指引。MCP 路线响应不包含道路顶点时，可以打开道路几何补充开关，使用同一高德 Key 调用官方 Web 服务路线接口；此时距离、耗时、指引和坐标均来自同一次官方路线响应，避免地图与行程数据不一致。

| 场景 | 数据来源 | 结果 |
| --- | --- | --- |
| POI 搜索、周边餐饮、地点详情、天气、专属地图 | 高德 MCP | 经过官方工具查询的地点与出行信息 |
| 道路折线 | 高德路线 Web 服务（可选） | 步行、驾车、骑行、公交的真实道路坐标 |
| Web 展示 | Leaflet + OpenStreetMap | 将高德 GCJ-02 坐标转换为 WGS-84 后渲染 |
| 小程序展示 | 微信原生 `map` | 直接使用 GCJ-02 坐标与 polyline |

> `AMAP_ROAD_GEOMETRY_ENABLED=true` 时启用道路折线补充。若接口暂不可用，界面只保留地点和明确提示，不绘制误导性的直线。

更完整的参数、容错和验证说明见 [高德 MCP 接入说明](doc/amap-mcp.md)。

## 技术架构

```mermaid
flowchart LR
    U[旅行者] --> W[Web 端 Vue 3]
    U --> M[微信小程序 uni-app]
    A[运营人员] --> C[管理后台 Vue 3]
    W --> B[FastAPI]
    M --> B
    C --> B
    B --> P[规划 Agent<br/>Plan → Execute → Finalize]
    P --> L[LLM Provider<br/>DeepSeek / OpenAI / Anthropic / Google]
    P --> G[高德 MCP]
    G --> R[高德路线 Web 服务<br/>可选道路坐标补充]
    B --> D[(MySQL)]
    B --> K[(Redis / 内存缓存)]
```

## 快速开始

### 1. 准备环境

- Python 3.12+
- Node.js 20+
- MySQL 8.0+
- 一个可用的 LLM API Key
- 高德 MCP Key；如需在 Web 和小程序地图上显示道路折线，还需要该 Key 具备高德 Web 服务路线权限

### 2. 克隆并初始化数据库

```bash
git clone https://github.com/xg-debug/ai-travel-planner.git
cd ai-travel-planner

# 创建数据库及基础表
mysql -u root -p < backend/schema.sql
```

### 3. 配置并启动后端

```bash
cp backend/.env.example backend/.env

# 编辑 backend/.env，至少填写 DATABASE_URL、一个 LLM Key 和高德 Key
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

最小地图和模型配置示例：

```env
DATABASE_URL=mysql+pymysql://root:your_mysql_password@127.0.0.1:3306/ai_travel_planner?charset=utf8mb4
SECRET_KEY=replace-with-a-long-random-secret

DEFAULT_LLM_PROVIDER=deepseek
DEFAULT_LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_deepseek_key

MAP_PROVIDER=amap_mcp
AMAP_MCP_URL=https://mcp.amap.com/mcp
AMAP_MCP_API_KEY=your_amap_key

# 启用 Web 与小程序的真实道路折线
AMAP_ROAD_GEOMETRY_ENABLED=true
```

其他模型可使用 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY` 或 `GOOGLE_API_KEY`，并在管理后台或环境变量中切换默认 Provider。

### 4. 启动 Web 端与管理后台

新开两个终端窗口：

```bash
# Web 行程端
cd frontend
npm install
npm run dev
```

```bash
# 管理后台
cd admin
npm install
npm run dev
```

访问：

| 服务 | 地址 |
| --- | --- |
| Web 行程端 | [http://localhost:5173](http://localhost:5173) |
| 管理后台 | [http://localhost:5174](http://localhost:5174) |
| API 文档 | [http://localhost:8000/api/docs](http://localhost:8000/api/docs) |
| 健康检查 | [http://localhost:8000/api/health](http://localhost:8000/api/health) |

### 5. 构建微信小程序

```bash
cd miniapp
npm install
npm run dev:mp-weixin
```

使用微信开发者工具导入 `miniapp/dist/dev/mp-weixin`。真机调试时，将 `miniapp/.env` 中的 API 地址改成开发机器可访问的局域网地址；生产环境需使用已配置到微信合法域名的 HTTPS 地址。

## 项目结构

```text
ai-travel-planner/
├── backend/                 # FastAPI、规划 Agent、MCP 与业务服务
│   ├── app/api/             # 行程、地图、认证、管理端接口
│   ├── app/trip_planning/   # Plan/Execute/Finalize 与任务进度
│   ├── app/mcp_tools/       # 高德 MCP Provider 与响应适配
│   ├── app/services/        # 路线、缓存、运行时配置
│   ├── tests/               # MCP、路线、Agent 测试
│   └── schema.sql           # MySQL 初始化脚本
├── frontend/                # Vue 3 Web 行程端
├── miniapp/                 # uni-app 微信小程序
├── admin/                   # Vue 3 管理后台
├── doc/                     # 安装、设计与地图接入文档
└── assets/readme/           # README 展示图片
```

## 接口概览

| 接口 | 用途 |
| --- | --- |
| `POST /api/trip/planning` | 创建行程规划 |
| `POST /api/trip/planning/stream` | 流式接收规划进度 |
| `POST /api/trip/planning/jobs` | 创建异步规划任务 |
| `GET /api/trip/plans` | 获取已保存行程 |
| `POST /api/trip/route/map` | 按交通方式计算每日道路路线 |
| `POST /api/trip/map/around` | 基于坐标搜索附近餐饮等 POI |
| `GET /api/trip/map/pois/{poi_id}` | 查询地点详情 |
| `POST /api/trip/map/export` | 导出高德专属地图 |

完整接口定义可在启动后访问 `/api/docs`。

## 开发与验证

```bash
# 后端测试
cd backend
.venv/bin/python -m unittest discover -s tests -q

# Web 构建
cd ../frontend
npm run build

# 管理端构建
cd ../admin
npm run build

# 小程序构建
cd ../miniapp
npm run build:mp-weixin
```

## 文档与反馈

- [安装与部署说明](doc/INSTALL.md)
- [高德 MCP 与道路路线接入](doc/amap-mcp.md)
- [详细设计](doc/detailed-design.md)
- [提交 Issue](https://github.com/xg-debug/ai-travel-planner/issues)

欢迎通过 Issue 提交问题、使用反馈和功能建议。
