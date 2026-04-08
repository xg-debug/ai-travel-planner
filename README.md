# 🌍 AI Travel Planner - 智能旅行规划系统

基于大模型的智能旅行规划系统，实现自动生成多日旅行行程、实时调用地图、天气等外部工具、支持个性化推荐、提供可视化地图与行程展示。

## ✨ 功能特性

### 🎯 核心功能
- **智能行程规划**: 基于大模型生成个性化多日旅行行程
- **实时地图集成**: 集成高德地图，展示景点位置和路线
- **天气预报**: 获取目的地实时天气和预报
- **个性化推荐**: 根据用户偏好推荐景点、美食、活动
- **预算估算**: 智能估算旅行费用，提供省钱建议
- **可视化展示**: 美观的界面展示行程、地图、天气等信息

### 🛠️ 技术栈

**后端 (Python)**
- FastAPI - 高性能Web框架
- LangChain/LangGraph - AI工作流编排
- 多LLM支持 (OpenAI, Anthropic, DeepSeek, Google)
- 高德地图API集成
- SQLAlchemy - 数据库ORM
- Redis - 缓存

**前端 (Vue 3)**
- Vue 3 + TypeScript
- Vite - 构建工具
- Ant Design Vue - UI组件库
- 高德地图JavaScript API
- Axios - HTTP客户端

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

### 3. 前端设置
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 或使用脚本
chmod +x start.sh
./start.sh
```

### 4. 访问应用
- 前端: http://localhost:5173
- 后端API文档: http://localhost:8000/docs
- 后端健康检查: http://localhost:8000/health

## 📁 项目结构

```
ai-travel-planner/
├── backend/                    # 后端代码
│   ├── app/
│   │   ├── api/               # API路由
│   │   │   └── trip.py        # 旅行相关API
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 配置文件
│   │   │   └── llm.py         # LLM工厂
│   │   ├── graph/             # LangGraph工作流
│   │   │   ├── graph.py       # 图定义
│   │   │   ├── nodes.py       # 节点函数
│   │   │   └── state.py       # 状态定义
│   │   ├── services/          # 业务服务
│   │   │   ├── amap_service.py    # 地图服务
│   │   │   ├── recommendation_service.py  # 推荐服务
│   │   │   └── budget_service.py   # 预算服务
│   │   └── main.py            # 应用入口
│   ├── requirements.txt       # Python依赖
│   ├── .env.example          # 环境变量示例
│   └── start.sh             # 启动脚本
│
├── frontend/                  # 前端代码
│   ├── src/
│   │   ├── components/       # Vue组件
│   │   │   ├── InputPanel.vue   # 输入面板
│   │   │   ├── ResultPanel.vue  # 结果面板
│   │   │   └── MapPanel.vue     # 地图面板
│   │   ├── services/         # API服务
│   │   │   └── api.ts        # API客户端
│   │   ├── App.vue           # 主应用
│   │   └── main.ts           # 入口文件
│   ├── package.json          # 依赖配置
│   ├── vite.config.ts        # Vite配置
│   └── start.sh             # 启动脚本
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
DEFAULT_LLM_PROVIDER=
DEFAULT_LLM_MODEL=
LLM_TEMPERATURE=
LLM_MAX_TOKENS=
```

#### 地图服务
```env
AMAP_API_KEY=your_amap_api_key
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

### 环境变量 (frontend/.env)
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AMAP_KEY=your_amap_key_here
```

## 📊 API接口

### 主要端点

#### 1. 规划行程
```http
POST /trip/plan
Content-Type: application/json

{
  "query": "家庭旅行，适合小朋友的景点",
  "city": "北京",
  "days": 3,
  "preferences": ["culture", "family"],
  "budget": "中等",
  "travelers": 4
}
```

#### 2. 获取天气
```http
GET /weather?city=北京&days=3
```

#### 3. 搜索POI
```http
GET /pois/search?keyword=故宫&city=北京&page=1&size=10
```

#### 4. 获取推荐
```http
GET /recommendations?city=北京&preferences=culture,food
```

#### 5. 估算预算
```http
POST /budget/estimate
Content-Type: application/json

{
  "itinerary": [...],
  "travelers": 4,
  "budget_level": "中等"
}
```

## 🎨 前端功能

### 主要界面

1. **首页**
   - 欢迎界面和系统介绍
   - 统计数据展示

2. **行程规划面板**
   - 目的地城市输入（带自动补全）
   - 旅行天数选择
   - 偏好选择（文化、美食、自然等）
   - 详细需求描述
   - 示例提示

3. **结果展示区**
   - 行程概览（天数、景点数、预计时间）
   - 每日详细安排（时间线展示）
   - 景点信息和实用建议
   - 加载动画和进度指示

4. **地图展示区**
   - 交互式地图显示景点位置
   - POI列表和详情查看
   - 地图控制（缩放、重置）
   - 路线规划

5. **推荐区域**
   - 个性化推荐卡片
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

如果没有配置API密钥，系统会使用模拟数据：

- **模拟POI数据**: 自动生成景点信息
- **模拟天气数据**: 生成未来几天的天气预报
- **模拟推荐数据**: 基于偏好生成推荐
- **模拟预算数据**: 根据预算水平估算费用

## 🚨 故障排除

### 常见问题

1. **后端启动失败**
   - 检查Python版本（需要3.8+）
   - 检查依赖安装：`pip install -r requirements.txt`
   - 检查端口占用：`lsof -i:8000`

2. **前端启动失败**
   - 检查Node.js版本（需要16+）
   - 清除node_modules重新安装：`rm -rf node_modules && npm install`

3. **地图不显示**
   - 检查高德地图API密钥配置
   - 检查网络连接
   - 查看浏览器控制台错误信息

4. **AI功能不可用**
   - 检查LLM API密钥配置
   - 检查网络连接（某些API需要科学上网）
   - 查看后端日志获取详细错误信息

### 日志查看

```bash
# 后端日志
cd backend
tail -f logs/app.log

# 前端日志
# 在浏览器开发者工具中查看Console和Network标签
```

## 📈 性能优化

### 缓存策略
- Redis缓存频繁查询的数据
- 浏览器本地存储用户偏好
- CDN加速静态资源

### 异步处理
- 使用Celery处理耗时任务
- 前端使用Web Workers处理大量数据
- 图片懒加载和代码分割

### 监控指标
- API响应时间
- 错误率监控
- 用户行为分析
- 系统资源使用情况

## 🔮 未来规划

### 短期计划
- [ ] 用户系统（登录、注册、保存行程）
- [ ] 更多地图提供商支持（百度地图、Google Maps）
- [ ] 实时交通信息
- [ ] 多语言支持

### 长期计划
- [ ] 移动端应用
- [ ] 社交分享功能
- [ ] AI导游语音助手
- [ ] VR/AR景点预览
- [ ] 智能拍照建议

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

**让AI为您规划完美的旅行！** ✈️🌴🏛️
