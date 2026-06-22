# 🌍 AI Travel Planner - 智能旅行规划系统

基于大模型的智能旅行规划系统，实现自动生成多日旅行行程、实时调用地图、天气等外部工具、支持个性化推荐、提供可视化地图与行程展示。

## ✨ 功能特性

### 🎯 核心功能
- **智能行程规划**: 基于大模型生成个性化多日旅行行程
- **实时地图集成**: 集成高德地图，展示景点位置和路线
- **天气预报**: 获取目的地实时天气和预报
- **个性化推荐**: 根据用户偏好推荐景点、美食、活动
- **预算估算**: 智能估算旅行费用，提供省钱建议
- **移动端展示**: 微信小程序展示行程、地图、天气、预算和历史记录

### 🛠️ 技术栈

**后端 (Python)**
- FastAPI - 高性能Web框架
- LangChain - LLM Provider 适配
- LangGraph Plan-Execute-Replan - 旅行规划工作流
- 多LLM支持 (OpenAI, Anthropic, DeepSeek, Google)
- 高德地图API集成
- SQLAlchemy - 数据库ORM
- Redis - 缓存

**小程序端 (uni-app)**
- uni-app + Vue 3 + TypeScript
- Pinia - 移动端状态管理
- 微信原生地图组件
- SSE 流式生成，失败时按错误类型兜底

**管理端 (Vue 3)**
- Vue 3 + TypeScript + Vite
- 运行时模型与地图配置管理

## 🚀 快速开始

### 环境要求
- Python 3.12
- Node.js 24
- Redis (可选)
- 高德地图API密钥

### 1. 克隆项目
```bash
git clone <repository-url>
cd ai-travel-planner
```

### 2. 后端设置
```bash
cd backend

# 环境变量文件
.env

# 编辑 .env 文件，配置您的API密钥
# 至少需要配置一个LLM API密钥（如OPENAI_API_KEY）
# 和高德地图API密钥（AMAP_API_KEY）

# 启动后端（使用脚本）
chmod +x start.sh
./start.sh

# 或手动启动
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 小程序设置
```bash
cd miniapp

# 安装依赖
npm install

# 微信小程序开发构建
npm run dev:mp-weixin

# 类型检查
npm run type-check
```

### 4. 管理端设置
```bash
cd admin
npm install
npm run dev
```

### 5. 访问应用
- 小程序: 使用微信开发者工具打开 `miniapp/dist/dev/mp-weixin`
- 管理端: http://localhost:5173
- 后端API文档: http://localhost:8000/docs
- 后端健康检查: http://localhost:8000/health

## 📁 项目结构

```
ai-travel-planner/
├── backend/                    # 后端代码
│   ├── app/
│   │   ├── api/               # API路由
│   │   │   ├── trip_planning.py   # 规划与异步任务
│   │   │   ├── trip_plans.py      # 行程保存与历史
│   │   │   └── map_routes.py      # 地图路线接口
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 配置文件
│   │   │   └── llm.py         # LLM工厂
│   │   ├── trip_planning/     # LangGraph 旅行规划工作流
│   │   │   ├── workflow.py    # TripPlanningWorkflow
│   │   │   ├── nodes.py       # Planner / Executor / Replanner / Finalizer 节点
│   │   │   ├── tool_executor.py # 天气、POI、住宿、交通工具执行
│   │   │   ├── state.py       # 请求归一化与进度状态
│   │   │   ├── jobs.py        # 异步任务状态
│   │   │   └── errors.py      # 规划错误分类
│   │   ├── mcp_tools/         # 地图 MCP/REST Provider
│   │   ├── services/          # 业务服务
│   │   │   ├── amap_service.py    # 地图服务
│   │   │   ├── map_route_service.py # 地图路线服务
│   │   │   └── runtime_config.py    # 运行时配置
│   │   └── main.py            # 应用入口
│   ├── requirements.txt       # Python依赖
│   ├── .env.example          # 环境变量示例
│   └── start.sh             # 启动脚本
│
├── miniapp/                   # 微信小程序端
│   ├── src/
│   │   ├── pages/            # 小程序页面
│   │   ├── components/       # 移动端组件
│   │   ├── services/         # uni.request / SSE 请求封装
│   │   ├── stores/           # Pinia 状态
│   │   └── utils/            # 行程转换与展示
│   └── package.json
│
├── admin/                     # 管理端
│   └── src/
│
└── README.md                 # 项目文档
```

## 🔧 配置说明

### 环境变量 (backend/.env)

#### LLM配置
```env
# 至少配置一个LLM提供商
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
GOOGLE_API_KEY=your_google_api_key

# 默认LLM配置
DEFAULT_LLM_PROVIDER=deepseek
DEFAULT_LLM_MODEL=deepseek-v4-flash
LLM_TEMPERATURE=
LLM_MAX_TOKENS=
```

#### 地图服务
```env
# 推荐：高德地图 MCP Server SSE
MAP_PROVIDER=amap_mcp_sse
AMAP_MCP_SSE_URL=your_amap_mcp_sse_url
AMAP_MCP_API_KEY=your_amap_mcp_key

# 备用：直接调用地图 REST API
AMAP_API_KEY=your_amap_api_key
TENCENT_MAP_API_KEY=your_tencent_map_key
UNSPLASH_ACCESS_KEY=your_unsplash_access_key
UNSPLASH_SECRET_KEY=your_unsplash_secret_key
```

#### 其他配置
```env
# 应用配置
DEBUG=true
PORT=8000

# 数据库
DATABASE_URL=mysql+pymysql://travel_user:travel_password@127.0.0.1:3306/ai_travel_planner?charset=utf8mb4

# 安全
SECRET_KEY=your-secret-key-change-in-production
```

### 环境变量 (miniapp/.env)
```env
VITE_API_BASE_URL=http://localhost:8000/api
```

## 📊 API接口

### 主要端点

#### 1. 规划行程
```http
POST /api/trip/planning
Content-Type: application/json

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
  "additionalRequirements": "家庭旅行，适合小朋友的景点"
}
```

#### 2. 流式规划
```http
POST /api/trip/planning/stream
```

#### 3. 异步任务规划
```http
POST /api/trip/planning/jobs
GET /api/trip/planning/jobs/{job_id}
```

#### 4. 行程管理
```http
GET /api/trip/plans
POST /api/trip/plans
GET /api/trip/plans/{id}
PUT /api/trip/plans/{id}
DELETE /api/trip/plans/{id}
```

#### 5. 地图路线
```http
POST /api/trip/route/map
```

## 🎨 小程序功能

### 主要界面

1. **用户需求页**：出发地、目的地、日期、人数、偏好、预算和住宿档位。
2. **生成中页**：SSE 真实进度；余额不足、密钥无效等不可重试错误会立即停止。
3. **行程总览页**：每日安排、推荐景点、美食推荐、酒店推荐、预算、往返交通。
4. **路线大图**：微信原生地图组件展示真实道路 polyline。
5. **地点详情页**：地点信息、参考价格、营业时间和站内地图定位。
6. **历史行程与登录页**：支持登录、保存和加载历史行程。
   - 基于偏好的智能推荐
   - 实用信息和建议

## 🔄 工作流程

```mermaid
graph TD
    A[用户输入需求] --> B[验证输入]
    B --> C[AI行程规划]
    C --> D[获取POI信息]
    D --> E[获取天气预报]
    E --> F[生成个性化推荐]
    E --> G[估算旅行预算]
    F --> H[生成最终总结]
    G --> H
    H --> I[返回完整行程]
```

## 🧪 测试数据

如果没有配置 API Key 或模型余额不足，系统会返回明确错误：

- `LLM_INSUFFICIENT_BALANCE`：模型账户余额不足，不会在小程序端反复重试。
- `LLM_INVALID_API_KEY`：模型密钥无效。
- `LLM_NOT_CONFIGURED`：未配置任何可用模型。
- 地图 Key 缺失时，路线和 POI 能力会降级或提示配置问题。

## 🚨 故障排除

### 常见问题

1. **后端启动失败**
   - 检查Python版本（需要3.8+）
   - 检查依赖安装：`pip install -r requirements.txt`
   - 检查端口占用：`lsof -i:8000`

2. **小程序构建失败**
   - 检查 Node.js 版本（建议 24）
   - 在 `miniapp/` 下重新安装依赖：`npm install`
   - 运行 `npm run type-check` 定位类型错误

3. **地图不显示**
   - 检查高德/腾讯地图 API Key 或高德 MCP SSE 配置
   - 检查网络连接
   - 查看微信开发者工具 Console 和 Network

4. **AI功能不可用**
   - 检查LLM API密钥配置
   - 检查网络连接（某些API需要科学上网）
   - 查看后端日志获取详细错误信息

### 日志查看

```bash
# 后端日志
cd backend
tail -f logs/app.log

# 小程序日志
# 在微信开发者工具中查看 Console 和 Network
```

## 📈 性能优化

### 缓存策略
- POI、天气、路线查询使用后端轻量缓存
- 小程序本地缓存最近一次行程和草稿
- 路线大图按天请求真实道路 polyline

### 异步处理
- SSE 优先推送真实规划进度
- 基础库不支持分块响应时，降级为异步 Job 状态接口
- 不可重试错误（余额不足、Key 无效）直接终止，不再重复发起任务

### 监控指标
- API 响应时间和规划耗时
- LLM 错误码、余额/Key 配置问题
- 地图路线真实 polyline 命中率
- 小程序生成失败率和重试率

## 🔮 未来规划

### 短期计划
- [ ] 接入更可靠的酒店价格/库存数据源
- [ ] 增加景点门票和营业时间的二次校验
- [ ] 完善行程编辑与分享卡片
- [ ] 增加路线规划命中率监控

### 长期计划
- [ ] 社交分享和协同行程
- [ ] AI导游语音助手
- [ ] 智能拍照建议

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

**让AI为您规划完美的旅行！** ✈️🌴🏛️
