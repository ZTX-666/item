import { computed, ref } from 'vue'

type Locale = 'zh-CN' | 'zh-TW'

const STORAGE_KEY = 'chitung-locale'
const initialLocale = localStorage.getItem(STORAGE_KEY) === 'zh-TW' ? 'zh-TW' : 'zh-CN'
const locale = ref<Locale>(initialLocale)

const traditionalText: Record<string, string> = {
  赤瞳安全智能平台: '赤瞳安全智能平台',
  开发者: '開發者',
  简体: '簡體',
  繁体: '繁體',
  赤瞳守护者: '赤瞳守護者',
  望风险: '望風險',
  视觉巡检总览: '視覺巡檢總覽',
  待确认事项: '待確認事項',
  隐患台账: '隱患台賬',
  视觉巡检: '視覺巡檢',
  闪闪文档: '閃閃文檔',
  书文档: '書文檔',
  文档审阅: '文檔審閱',
  智能填表: '智能填表',
  表格映射: '表格映射',
  报告生成: '報告生成',
  赤瞳聆讯: '赤瞳聆訊',
  闻动态: '聞動態',
  数据浏览: '數據瀏覽',
  命令工具: '命令工具',
  工作台总览: '工作台總覽',
  系统设置: '系統設置',
  AI助手: 'AI 助手',
  自动化: '自動化',
  技能: '技能',
  工作流: '工作流',
  耀耀慧读: '耀耀慧讀',
  问制度: '問制度',
  结构化输入: '結構化輸入',
  耀耀知识: '耀耀知識',
  外部风险: '外部風險',
  五大板块: '五大板塊',
}

export function useLocale() {
  const isTraditional = computed(() => locale.value === 'zh-TW')

  function setLocale(next: Locale) {
    locale.value = next
    localStorage.setItem(STORAGE_KEY, next)
  }

  function toggleLocale() {
    setLocale(locale.value === 'zh-CN' ? 'zh-TW' : 'zh-CN')
  }

  function display(text: string): string {
    return isTraditional.value ? traditionalText[text] ?? text : text
  }

  return {
    locale,
    isTraditional,
    setLocale,
    toggleLocale,
    display,
  }
}
