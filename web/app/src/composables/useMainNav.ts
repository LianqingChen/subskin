import { computed } from 'vue'
import { useRoute } from 'vue-router'
import siteModulesJson from '../../../shared/site-modules.json'

/**
 * 主导航（顶栏 / 桌面侧边栏 / 手机底部导航共用）。
 * 命名/图标与后端导航解析共用同一份清单（web/shared/site-modules.json），保持命名一致。
 * 主导航顺序：问答 · 记录 · 发现 · 同行。调养入口暂隐藏，页面与清单保留。
 */
interface SiteModule { path: string; label: string; icon: string }
const NAV_PATHS = ['/', '/assessment', '/community', '/contribution'] as const
/** 不属于主模块、路由也没有 meta.title 的页面，桌面顶栏标题兜底 */
const EXTRA_LABELS: [string, string][] = [
  ['/profile', '我的'],
  ['/user/', '用户主页'],
  ['/collection/', '合集'],
  ['/photo-guide', '拍照指南'],
  ['/privacy', '隐私政策'],
  ['/terms', '服务条款'],
  ['/share/', '白斑报告'],
]

export function useMainNav() {
  const route = useRoute()

  const navItems = computed(() => {
    const mods = siteModulesJson.modules as SiteModule[]
    return NAV_PATHS.map((p) => {
      const m = mods.find((x) => x.path === p)
      return { path: p, label: m?.label ?? '', iconClass: m?.icon ?? '' }
    }).filter((x) => x.label !== '')
  })

  function isNavActive(path: string): boolean {
    if (path === '/') return route.path === '/'
    // 记录: /assessment 及其子页、体检详情（/tracker/）、白斑对比与报告详情（/community/reports/*）
    if (path === '/assessment') {
      return route.path === '/assessment' || route.path.startsWith('/assessment/') ||
        route.path.startsWith('/tracker') || route.path.startsWith('/community/reports')
    }
    // 发现: /community/reports/* 属于「记录」域（白斑对比/报告），不算发现；就医经验（/hospitals）归属发现
    if (path === '/community') {
      return route.path === '/community' || route.path.startsWith('/hospitals') || route.path.startsWith('/discover') ||
        (route.path.startsWith('/community/') && !route.path.startsWith('/community/reports'))
    }
    return route.path === path || route.path.startsWith(path + '/')
  }

  /** 当前所在主模块的名称（桌面顶栏标题用）；不属于任何主模块时取路由标题 */
  const currentLabel = computed(() => {
    const hit = navItems.value.find((item) => isNavActive(item.path))
    if (hit) return hit.label
    if (route.meta.title) return String(route.meta.title)
    const fallback = EXTRA_LABELS.find(([prefix]) => route.path.startsWith(prefix))
    return fallback ? fallback[1] : ''
  })

  return { navItems, isNavActive, currentLabel }
}
