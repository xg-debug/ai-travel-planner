# 高德官方 MCP 接入

应用默认通过官方 `https://mcp.amap.com/mcp` 以 Streamable HTTP 连接，使用 Python MCP SDK 完成 initialize 和 tools/call。POI、周边搜索、详情、天气和专属地图导出使用 MCP。道路折线另有可选的 Web 服务补充模块，默认关闭。

配置：

```env
MAP_PROVIDER=amap_mcp
AMAP_MCP_URL=https://mcp.amap.com/mcp
AMAP_MCP_API_KEY=你的高德Key
AMAP_MCP_MAX_QPS=2
```

后台 `map.amap_mcp.api_key` 优先，其次 `AMAP_MCP_API_KEY`、后台旧 `map.amap.api_key`、`AMAP_API_KEY`。旧 provider 名称 `amap`、`amap_mcp_sse` 自动映射到 `amap_mcp`；旧 SSE URL 被忽略。Key 只在后端使用，HTTP 请求日志不记录携带 Key 的地址，错误信息不透传 SDK URL。`mcp.amap.com` 是唯一允许的 MCP 主机。

## 能力映射

| 业务工具 | 官方 MCP 工具 |
| --- | --- |
| geocode_pois | maps_text_search + maps_search_detail |
| around_search | maps_around_search + maps_search_detail |
| poi_detail | maps_search_detail |
| get_weather_forecast | maps_weather |
| plan_route | maps_direction_walking / maps_direction_bicycling / maps_direction_driving / maps_direction_transit_integrated |
| personal_map | maps_schema_personal_map |

官方关键词搜索结果可能没有经纬度。搜索适配器按 POI ID 继续取详情，补全坐标、地址、照片、营业时间、评分、参考消费。详情失败时保留搜索证据，但不会标记为已核对或生成假坐标。餐饮搜索优先围绕最多 3 个景点和 2 个酒店，各取 1.5 公里内的真实餐厅，结果不足时补充城市关键词搜索。

路线使用同一个领域服务和缓存；缓存区分起终点、模式、公交城市以及 Provider。行程生成完成后补充每日交通数据和活动间交通说明，地图页面复用相同缓存。公交需要城市参数；显式选择某种交通方式失败时不会偷偷换成其他方式。自动推荐模式按距离选择步行或驾车。

官方 MCP 当前的实测路线响应含距离、耗时和逐段指引，但不含道路折线，工具参数也没有折线返回开关。返回 `geometry_available=false` 时，网页和小程序只显示地点，不将地点直线相连。

网页使用 Leaflet + OpenStreetMap 真实底图，支持缩放、拖动、地点选择和路线范围定位。高德的 GCJ-02 坐标在渲染时统一转换为 WGS-84，避免标记与道路偏移；后端和微信地图继续使用 GCJ-02。底图保留可见署名，按视口正常请求图块，不预下载。可用 `VITE_MAP_TILE_URL` 和 `VITE_MAP_ATTRIBUTION` 配置适合部署环境的底图服务。

需要高德道路折线时，可启用 `AMAP_ROAD_GEOMETRY_ENABLED=true`，将现有高德 Web 服务 Key 用于官方路线 REST 接口。MCP 无折线或暂时不可用时补充驾车、步行、骑行和公交几何，并同时采用这次路线响应中的距离、耗时和指引，确保规划和地图使用同一方案。配置模板默认关闭；本地环境已按用户授权开启，并于 2026-09-08 使用现有 Key 完成四种交通方式、自动推荐及地图接口的真实联调。道路补充失败不会缓存缺少折线的结果，手动重试可立即重新查询。未取得坐标的路段不绘制假路线；不同路线步骤的坐标组分别绘制，不强行连接不连续段。

参考：[高德路线接口](https://lbs.amap.com/api/webservice/guide/api/direction)、[Leaflet](https://leafletjs.com/examples/quick-start/)、[OSM 图块使用规则](https://operations.osmfoundation.org/policies/tiles/)。

## HTTP 接口

- `POST /api/trip/route/map`：`{mode, city, cityd?, segments:[{dayIndex, points:[{latitude,longitude,title?}]}]}`。mode 为 touring、walking、driving、bicycling 或 transit。
- `POST /api/trip/map/around`：`{point:{latitude,longitude}, keyword:"餐厅", radius:1500}`，返回 `{pois:[...]}`。
- `GET /api/trip/map/pois/{poi_id}`：返回核对后的地点。
- `POST /api/trip/map/export`：`{title, segments:[{dayIndex,title,points:[{latitude,longitude,title,poiId}]}]}`，按日保留点位顺序，返回 `{url,provider}`。

专属地图通过用户点击导出触发；不会在行程生成时自动导出。网页版提供返回的高德唤端链接；微信小程序复制链接，让用户在浏览器中打开进入高德。高德要求每个导出点位有非空 POI ID；历史行程缺少 ID 时，通过 MCP 周边搜索和详情寻找 500 米内唯一同名地点，核对成功后补全 ID。无匹配或匹配不唯一时返回 422 并指出具体地点，不替换成不确定的地点。

## 验证

工具调用在单个后端进程内统一限速，默认每秒 2 次，可用 `AMAP_MCP_MAX_QPS` 调整。收到高德 `CUQPS_HAS_EXCEEDED_THE_LIMIT` 等频率限制时，只读查询最多尝试 3 次并退避等待；地图导出不自动重放。日志只记录 MCP 工具名、传输协议与重试次数，不记录 Key 或请求参数。

模型不可用时，基础行程响应通过 `planning_warnings` 披露降级原因，网页与小程序展示该提示；保存行程时通过 `planningWarnings` 保留。余额不足仍需处理模型账户配置才能恢复完整 AI 规划。

```sh
cd backend
.venv/bin/python -m unittest discover -s tests -q
```

测试覆盖稀疏 POI 补全、官方天气及公交格式、无折线路线、明确交通方式失败处理、分段几何、凭据错误脱敏、旧配置迁移、多日导出、坐标校验、周边搜索及缓存区分。

官方参考：[能力说明](https://lbs.amap.com/api/mcp-server/summary)、[接入指南](https://lbs.amap.com/api/mcp-server/gettingstarted)、[SSE 下线记录](https://lbs.amap.com/api/mcp-server/changelog)。
