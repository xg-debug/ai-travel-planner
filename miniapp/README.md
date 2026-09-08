# AI Travel Planner Miniapp

这是 AI Travel Planner 的微信小程序展示层，与 `frontend/` Web 端共用同一套旅行规划接口和视觉语言。

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

`localhost` 只适用于微信开发者工具。真机中的 `localhost` 指手机本身，真机调试请改成电脑局域网 IP（例如 `http://192.168.1.10:8000/api`）；正式发布必须使用已加入微信 request 合法域名的 HTTPS 地址。

线上微信小程序必须使用 HTTPS 后端域名，并在微信公众平台配置 request 合法域名。

景点、餐饮和酒店实景图来自地图 POI 数据。若微信管理后台启用了图片域名校验，还需要把下面两个 HTTPS 域名加入图片/downloadFile 合法域名：

- `https://store.is.autonavi.com`
- `https://aos-comment.amap.com`

第三方图片不可用时，小程序会自动使用 `src/static/recommendations/` 中的本地旅行主题图。

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

- `POST /api/trip/planning/stream`
- `POST /api/trip/planning/jobs`
- `GET /api/trip/planning/jobs/{job_id}`
- `POST /api/trip/plans`
- `GET /api/trip/plans`
- `GET /api/trip/plans/{id}`
- `PUT /api/trip/plans/{id}`
- `DELETE /api/trip/plans/{id}`
- `POST /api/trip/route/map`
- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/auth/me`

生成页优先使用 `/api/trip/planning/stream` 获取真实进度；如果微信基础库不支持分块响应，会降级到异步任务接口。余额不足、密钥无效、未配置模型等不可重试错误会直接终止生成，不再反复重试。
