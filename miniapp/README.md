# AI Travel Planner Miniapp

这是 AI Travel Planner 的小程序展示层。现有 `frontend/` Web 端保持不变，小程序端独立维护页面、请求封装和移动端状态。

## 技术栈

- uni-app
- Vue 3
- TypeScript
- Pinia

## 目录

```text
miniapp/
├── src/
│   ├── pages/          # 小程序页面
│   ├── components/     # 移动端展示组件
│   ├── services/       # uni.request 请求封装
│   ├── stores/         # Pinia 状态
│   ├── types/          # 行程和认证类型
│   ├── utils/          # 格式化与行程转换
│   ├── pages.json      # 页面与 tabBar
│   └── manifest.json   # 小程序配置
└── package.json
```

## 环境变量

复制 `.env.example` 为 `.env`，并配置后端地址：

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

线上微信小程序必须使用 HTTPS 后端域名，并在微信公众平台配置 request 合法域名。

## 常用命令

```bash
npm --prefix miniapp install
npm --prefix miniapp run dev:mp-weixin
npm --prefix miniapp run build:mp-weixin
npm --prefix miniapp run type-check
```

## 第一版页面

- `pages/plan/index`：旅行规划表单
- `pages/generating/index`：AI 生成进度
- `pages/trip-detail/index`：行程总览
- `pages/day-detail/index`：当日时间线
- `pages/place-detail/index`：地点详情
- `pages/trips/index`：历史行程
- `pages/profile/index`：我的
- `pages/auth/index`：登录注册

## 后端接口

小程序端复用现有后端接口：

- `POST /api/trip/plan`
- `POST /api/trip/plans`
- `GET /api/trip/plans`
- `GET /api/trip/plans/{id}`
- `DELETE /api/trip/plans/{id}`
- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/auth/me`

第一版生成页使用非流式 `/api/trip/plan`，同时在前端展示本地步骤进度。后续如果需要真实进度，再接入 `/api/trip/plan/stream`。
