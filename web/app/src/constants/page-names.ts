/**
 * ⚠️ SINGLE SOURCE OF TRUTH for page/feature names.
 *
 * When any page or feature is renamed in the app, update this file FIRST,
 * then ensure web/shared/page-names.json and the backend analytics.py
 * _normalize() function / get_feature_usage() names are also updated.
 *
 * This file mirrors web/shared/page-names.json for the frontend.
 * The backend reads the JSON directly.
 */

/** Map URL path prefix → display name for user journey / path analysis */
export const PATH_TO_PAGE_NAME: Record<string, string> = {
  '/': '问答',
  '/chat': '问答',
  '/assessment': '记录',
  '/tracker': '记录',
  '/community': '发现',
  '/hospitals': '就医经验',
  '/care': '调养',
  '/contribution': '同行',
  '/discover': '发现',
  '/encyclopedia': '百科（已下线）',
  '/wiki-content': '百科（已下线）',
  '/knowledge': '百科（已下线）',
  '/profile': '个人中心',
  '/privacy': '隐私政策',
  '/terms': '服务条款',
}

export const FEATURE_NAMES = {
  aiChat: 'AI问答',
  vasi: '追踪评估',
  reportUpload: '上传体检报告',
  post: '发帖',
  comment: '评论',
  like: '点赞',
} as const

export const NORTH_STAR = {
  label: '注册用户数',
  subtitle: '累计注册用户数',
} as const

/**
 * Normalize a URL path to a user-facing page name.
 * Falls back to path with query string removed for unknown routes.
 */
export function normalizePagePath(path: string): string {
  if (PATH_TO_PAGE_NAME[path]) return PATH_TO_PAGE_NAME[path]

  for (const [prefix, name] of Object.entries(PATH_TO_PAGE_NAME)) {
    if (prefix !== '/' && prefix !== '/chat' && path.startsWith(prefix)) {
      return name
    }
  }

  return path.split('?')[0]
}
