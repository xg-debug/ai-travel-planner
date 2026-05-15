export interface TravelIntent {
  destination: string
  additionalRequirements: string
}

const CITY_DESTINATIONS = [
  '北京',
  '上海',
  '广州',
  '深圳',
  '杭州',
  '南京',
  '苏州',
  '成都',
  '重庆',
  '武汉',
  '西安',
  '长沙',
  '青岛',
  '厦门',
  '福州',
  '泉州',
  '宁波',
  '温州',
  '无锡',
  '常州',
  '扬州',
  '南通',
  '天津',
  '大连',
  '沈阳',
  '哈尔滨',
  '长春',
  '济南',
  '烟台',
  '威海',
  '郑州',
  '洛阳',
  '开封',
  '太原',
  '石家庄',
  '合肥',
  '南昌',
  '昆明',
  '大理',
  '丽江',
  '西双版纳',
  '贵阳',
  '遵义',
  '南宁',
  '桂林',
  '北海',
  '海口',
  '三亚',
  '拉萨',
  '林芝',
  '西宁',
  '兰州',
  '敦煌',
  '银川',
  '呼和浩特',
  '乌鲁木齐',
  '喀什',
  '香港',
  '澳门',
  '台北',
  '高雄',
  '垦丁',
  '舟山',
  '黄山',
  '婺源',
  '张家界',
  '凤凰',
  '恩施',
  '宜昌',
  '九江',
  '景德镇',
  '秦皇岛',
  '承德',
  '阿勒泰',
  '伊犁',
  '吐鲁番',
  '呼伦贝尔',
  '漠河',
  '延吉',
  '长白山'
].sort((a, b) => b.length - a.length)

const REGION_DESTINATIONS = [
  '广东',
  '浙江',
  '江苏',
  '四川',
  '云南',
  '贵州',
  '广西',
  '海南',
  '福建',
  '山东',
  '河南',
  '河北',
  '湖北',
  '湖南',
  '江西',
  '安徽',
  '陕西',
  '山西',
  '甘肃',
  '青海',
  '宁夏',
  '新疆',
  '西藏',
  '内蒙古',
  '东北',
  '华东',
  '川西'
].sort((a, b) => b.length - a.length)

const GENERIC_DESTINATIONS = new Set([
  '海边',
  '沙滩',
  '草原',
  '雪山',
  '古镇',
  '山里',
  '海岛',
  '温泉',
  '景点',
  '城市',
  '周边'
])

const normalizeInput = (value: string) =>
  String(value || '')
    .replace(/\s+/g, '')
    .replace(/[!?！？。；;]+$/g, '')
    .trim()

const stripAdministrativeSuffix = (value: string) =>
  value.replace(/(特别行政区|自治区|自治州|地区|市|省|县|区)$/g, '')

const findKnownDestination = (text: string) => {
  const city = CITY_DESTINATIONS.find((item) => text.includes(item))
  if (city) return city
  return REGION_DESTINATIONS.find((item) => text.includes(item)) || ''
}

const extractDestinationByPattern = (text: string) => {
  const patterns = [
    /(?:想去|要去|准备去|计划去|打算去|一个人去|和.+?去|去|到|前往)([\u4e00-\u9fa5]{2,12}?)(?:旅游|旅行|游玩|玩|逛|看|吃|住|，|,|。|\.|、|和|并|$)/,
    /([\u4e00-\u9fa5]{2,12}?)(?:旅游|旅行|[0-9一二三四五六七八九十]+日游)/
  ]

  for (const pattern of patterns) {
    const matched = text.match(pattern)
    const destination = stripAdministrativeSuffix(matched?.[1] || '')
    if (destination && !GENERIC_DESTINATIONS.has(destination)) return destination
  }
  return ''
}

export const parseTravelIntent = (input: string): TravelIntent => {
  const cleaned = normalizeInput(input)
  if (!cleaned) return { destination: '', additionalRequirements: '' }

  const exactDestination = stripAdministrativeSuffix(cleaned)
  if (/^[\u4e00-\u9fa5A-Za-z·]{2,20}$/.test(cleaned) && !/[我想要准备计划打算去到玩游逛看吃住，,、]/.test(cleaned)) {
    return { destination: exactDestination, additionalRequirements: '' }
  }

  const destination = findKnownDestination(cleaned) || extractDestinationByPattern(cleaned)
  return {
    destination,
    additionalRequirements: destination && destination !== cleaned ? cleaned : ''
  }
}
