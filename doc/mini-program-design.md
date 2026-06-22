# AI Travel Planner 小程序端设计方案

## 1. 目标

在保留现有 Web 前端的前提下，新增一套面向手机用户的小程序展示层。小程序不重写后端能力，仍调用当前已经实现的 API，包括行程生成、流式进度、天气、POI、历史行程、登录注册等接口。

核心原则：

1. Web 端继续作为桌面和 H5 访问入口。
2. 小程序端作为独立前端工程，不直接迁移 Web UI。
3. 复用接口契约、数据类型、业务转换逻辑，UI 按小程序交互习惯重新设计。
4. 第一版小程序优先完成“生成行程、查看行程、历史行程、个人中心”闭环。

## 2. 推荐技术路线

推荐使用 `uni-app + Vue 3 + TypeScript` 建小程序端。

原因：

1. 当前 Web 前端已经是 Vue 3，团队心智和组件写法更接近。
2. `uni-app` 可同时发布微信小程序和 H5，后续如果想做移动 H5 也能复用一部分页面。
3. 小程序端请求、存储、路由、生命周期与 Web 不同，独立工程能减少对现有 Web 的破坏。

建议目录：

```text
ai-travel-planner/
├── miniapp/                 # 新增小程序端
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/
│   │   ├── stores/
│   │   ├── utils/
│   │   └── types/
│   ├── pages.json
│   ├── manifest.json
│   └── package.json
└── shared/                  # 后续可选：沉淀跨端共享类型和转换函数
    └── trip/
```

第一阶段也可以先不建 `shared/` 包，直接在 `miniapp/src/types` 和 `miniapp/src/services` 中复制接口契约，等小程序稳定后再抽公共包。

## 3. 小程序信息架构

小程序不建议复刻 Web 首页的大横幅和复杂布局，应改成任务导向的手机工作流。

底部 Tab 建议：

| Tab | 页面 | 说明 |
| --- | --- | --- |
| 规划 | `pages/plan/index` | 默认首页，快速输入旅行需求 |
| 行程 | `pages/trips/index` | 历史行程、草稿、最近生成 |
| 我的 | `pages/profile/index` | 登录、账号、设置 |

二级页面：

| 页面 | 路径 | 说明 |
| --- | --- | --- |
| 生成中 | `pages/generating/index` | 展示 AI 多步骤进度 |
| 行程详情 | `pages/trip-detail/index` | 行程总览、预算、天气、每日安排 |
| 当日详情 | `pages/day-detail/index` | 单日时间线、景点、餐饮、住宿 |
| 地点详情 | `pages/place-detail/index` | POI、地址、价格、提示 |
| 登录注册 | `pages/auth/index` | 邮箱登录、注册、找回密码 |

## 4. 核心页面设计

### 4.1 规划页

目标：让用户在 30 秒内提交一次可用规划。

布局：

1. 顶部展示一句明确标题：`想去哪玩？`
2. 第一屏放核心输入：
   - 目的地
   - 出发日期
   - 天数
   - 人数
3. 第二屏放偏好和预算：
   - 预算档位：经济、舒适、豪华
   - 兴趣标签：文化、美食、自然、亲子、购物、轻松
   - 补充需求文本框
4. 底部固定主按钮：`生成行程`

交互：

1. 表单使用分组卡片，不做 Web 式三列布局。
2. 日期、人数、天数用小程序原生 picker/stepper。
3. 偏好使用可点选 chip。
4. 提交后跳转到生成中页面。

### 4.2 生成中页面

目标：让用户知道 AI 正在做什么，降低等待焦虑。

内容：

1. 顶部：目的地、天数、人数摘要。
2. 中部：步骤进度列表。
3. 底部：生成完成后自动进入行程详情。

步骤沿用 Web 端已有状态：

| step | 展示文案 |
| --- | --- |
| `request_analysis` | 拆解旅行需求 |
| `weather_lookup` | 获取天气 |
| `attraction_search` | 搜索景点 |
| `food_search` | 安排餐饮 |
| `hotel_search` | 推荐住宿 |
| `candidate_scoring` | 评分排序 |
| `transport_planning` | 评估动线 |
| `itinerary_synthesis` | 生成每日行程 |
| `route_grounding` | 校准真实地点 |
| `poi_enrichment` | 补全地点信息 |
| `itinerary_review` | 审查行程质量 |
| `budget_estimation` | 计算预算 |
| `risk_notices` | 生成提醒 |
| `summary` | 整理结果 |

注意：

微信小程序环境下流式响应需要单独处理。当前优先调用 `/api/trip/planning/stream`，使用小程序分块读取能力展示真实进度；如果基础库不支持分块响应，再降级到 `/api/trip/planning/jobs`。

### 4.3 行程详情页

目标：手机上先看结论，再逐步展开细节。

页面结构：

1. 顶部摘要：
   - 目的地
   - 日期范围
   - 人数
   - 总预算
2. 快捷模块：
   - 天气
   - 预算
   - 住宿
   - 地图
3. 每日行程列表：
   - 第 1 天、第 2 天、第 3 天
   - 每天展示 2 到 3 个关键地点
   - 点击进入当日详情
4. 底部操作：
   - 分享行程
   - 保存行程
   - 重新规划

展示形式：

1. 不在详情页一次性铺满全部活动，避免手机滚动过长。
2. 每日行程用“日期卡 + 活动摘要”的形式。
3. 预算用简洁条形分布，突出住宿、餐饮、交通、门票。
4. 天气用横向滑动卡片展示每天预报。

### 4.4 当日详情页

目标：用户当天出行时可以直接照着走。

内容：

1. 顶部：第几天、日期、当日预算。
2. 时间线：
   - 时间
   - 活动标题
   - 地点
   - 预计花费
   - 门票信息
   - 停留时长
3. 分组展示：
   - 景点安排
   - 餐饮安排
   - 住宿推荐
   - 其他提醒

交互：

1. 点击活动进入地点详情。
2. 地点有坐标时，调用小程序地图能力打开位置。
3. 后续版本再支持编辑排序、添加活动、删除活动。

### 4.5 历史行程页

目标：承接登录用户的行程资产。

内容：

1. 最近生成的行程置顶。
2. 行程列表展示目的地、日期、天数、预算。
3. 支持删除和重新打开。

未登录状态：

1. 显示本地最近一次生成结果。
2. 引导登录后云端保存。

### 4.6 我的页面

目标：完成登录与账户操作，不做复杂设置。

内容：

1. 未登录：登录、注册入口。
2. 已登录：头像、昵称、邮箱。
3. 功能入口：
   - 我的行程
   - 清理本地缓存
   - 退出登录

## 5. 接口映射

小程序端继续调用当前后端接口。

| 功能 | 方法 | 接口 | 说明 |
| --- | --- | --- | --- |
| 注册 | `POST` | `/api/auth/register` | 邮箱注册 |
| 登录 | `POST` | `/api/auth/login` | 返回 token |
| 获取当前用户 | `GET` | `/api/auth/me` | 进入小程序时恢复登录 |
| 修改用户 | `PUT` | `/api/users/me` | 更新昵称头像 |
| 流式生成 | `POST` | `/api/trip/planning/stream` | 当前推荐使用 |
| 异步生成 | `POST` | `/api/trip/planning/jobs` | SSE 不可用时降级 |
| 任务状态 | `GET` | `/api/trip/planning/jobs/{job_id}` | 查询进度和结果 |
| 保存行程 | `POST` | `/api/trip/plans` | 登录后保存 |
| 历史行程 | `GET` | `/api/trip/plans` | 登录后使用 |
| 行程详情 | `GET` | `/api/trip/plans/{id}` | 打开历史行程 |
| 更新行程 | `PUT` | `/api/trip/plans/{id}` | 后续编辑能力 |
| 删除行程 | `DELETE` | `/api/trip/plans/{id}` | 历史页使用 |
| 地图路线 | `POST` | `/api/trip/route/map` | 路线大图真实道路 polyline |
| 路线计算 | `POST` | `/api/trip/route/calculate` | 后续地点导航 |

## 6. 请求封装

小程序端需要重新封装 API Client，不能直接复用 Web 端的 axios 拦截器。

建议封装：

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export function request<T>(options: {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: unknown
  params?: Record<string, string | number | boolean | undefined>
}): Promise<T> {
  const token = uni.getStorageSync('cybertravel_auth_token')
  return new Promise((resolve, reject) => {
    uni.request({
      url: buildUrl(`${API_BASE_URL}${options.url}`, options.params),
      method: options.method || 'GET',
      data: options.data,
      timeout: 180000,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
          return
        }
        reject(new Error(parseApiError(res.data, res.statusCode)))
      },
      fail: () => reject(new Error('网络连接异常，请稍后重试'))
    })
  })
}
```

## 7. 状态管理

小程序端可继续使用 Pinia，但状态需要更轻。

建议 Store：

| Store | 责任 |
| --- | --- |
| `authStore` | token、用户信息、登录状态 |
| `tripStore` | 当前行程、历史行程、生成状态 |
| `draftStore` | 规划页表单草稿 |

本地存储键：

| key | 内容 |
| --- | --- |
| `cybertravel_auth_token` | 登录 token |
| `cybertravel_user` | 用户信息 |
| `cybertravel_last_trip` | 最近一次生成结果 |
| `cybertravel_plan_draft` | 未提交表单草稿 |

## 8. 与 Web 端的复用边界

可以复用：

1. API 路径和请求参数。
2. `TripResponse`、`Trip`、`TripDay`、`Activity` 等类型。
3. `mapBudgetLevel`、`convertItineraryToDays`、`convertWeatherToForecast`、`convertBudgetBreakdown` 等转换逻辑。
4. 错误文案规范。
5. 登录 token 的 Bearer 认证方式。

不建议复用：

1. Web 的页面组件和布局。
2. `axios` 拦截器。
3. `localStorage/sessionStorage` 相关实现。
4. `html2canvas`、`jspdf`、`three`、`gsap` 相关能力。
5. Web 地图页的 3D 可视化。

## 9. 小程序第一版范围

P0：

1. 规划页提交行程。
2. 生成中页面。
3. 行程详情页。
4. 当日详情页。
5. 登录、注册、退出。
6. 历史行程列表。
7. 调用后端保存和读取历史。

P1：

1. 分享行程卡片。
2. 小程序地图打开地点。
3. 行程编辑、活动排序。
4. 图片导出或长图分享。

P2：

1. 真实流式进度。
2. 微信一键登录。
3. 订阅消息。
4. 支付、门票、酒店跳转。

## 10. 实施步骤

### 第一步：新增 miniapp 工程

1. 使用 `uni-app + Vue 3 + TypeScript` 初始化。
2. 配置 `pages.json`、`manifest.json`。
3. 配置后端 API 域名环境变量。
4. 实现基础请求封装和 token 注入。

### 第二步：迁移接口契约

1. 小程序端在 `miniapp/src/types/trip.ts` 维护当前接口契约。
2. 小程序端使用 `miniapp/src/services/tripApi.ts` 封装 `uni.request`、SSE 和异步任务降级。
3. 行程转换逻辑维护在 `miniapp/src/utils/tripTransform.ts`。

### 第三步：完成 P0 页面

1. 规划页。
2. 生成中页。
3. 行程详情页。
4. 当日详情页。
5. 历史行程页。
6. 我的页和登录页。

### 第四步：联调后端

1. 确认后端部署到 HTTPS。
2. 微信公众平台配置 request 合法域名。
3. 验证登录 token、生成行程、保存历史。
4. 验证超时设置，AI 生成接口建议保留 180 秒。

### 第五步：发布前检查

1. 手机小屏可读性。
2. 长行程滚动性能。
3. 未登录和登录状态一致性。
4. 后端错误文案是否友好。
5. 网络慢、生成失败、token 过期的兜底状态。

## 11. 风险与处理

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| 小程序对流式响应支持不如 Web 稳定 | 生成进度可能不实时 | 第一版用非流式接口 + 本地步骤动画 |
| AI 生成耗时较长 | 小程序请求可能超时 | 后端保留任务状态接口会更稳，第一版先使用长 timeout |
| Web 组件无法直接复用 | 迁移成本增加 | 复用业务逻辑，不复用页面 UI |
| 地图能力差异 | 3D 地图不能迁移 | 小程序使用原生地图或打开位置 |
| 分享和导出能力不同 | PDF 导出不适合小程序 | 优先做行程分享卡片和长图 |

## 12. 结论

当前最合适的方案是：

1. 删除旧 `frontend/` Web 展示端。
2. 保留 `miniapp/` 作为主要用户端。
3. 保留 `admin/` 作为运行时配置与管理端。
4. 后端 API 以 `/api/trip/planning/stream`、`/api/trip/planning/jobs` 和 `/api/trip/plans` 为主。
5. 后续如需跨端复用，再抽取共享类型和转换函数。

这样可以减少重复前端维护成本，把产品体验集中到真正面向用户的小程序端。
