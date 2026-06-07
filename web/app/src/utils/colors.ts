/**
 * Category color utility — uses CSS variables for theme-aware colors.
 * Replaces hardcoded Tailwind native colors (bg-blue-100, text-green-700, etc.)
 * with semantic primary-* variants so all color tokens follow the user's theme hue.
 */

export interface CategoryColor {
  bg: string
  text: string
  darkBg: string
  darkText: string
}

const CATEGORY_COLORS: Record<string, CategoryColor> = {
  '治疗分享': {
    bg: 'bg-primary-100',
    text: 'text-primary-700',
    darkBg: 'dark:bg-primary-900/40',
    darkText: 'dark:text-primary-300',
  },
  '心理支持': {
    bg: 'bg-primary-200',
    text: 'text-primary-800',
    darkBg: 'dark:bg-primary-900/50',
    darkText: 'dark:text-primary-200',
  },
  '护肤经验': {
    bg: 'bg-primary-50',
    text: 'text-primary-600',
    darkBg: 'dark:bg-primary-900/30',
    darkText: 'dark:text-primary-300',
  },
  '日常饮食': {
    bg: 'bg-primary-100',
    text: 'text-primary-700',
    darkBg: 'dark:bg-primary-900/40',
    darkText: 'dark:text-primary-300',
  },
  '诊断咨询': {
    bg: 'bg-primary-200',
    text: 'text-primary-800',
    darkBg: 'dark:bg-primary-900/50',
    darkText: 'dark:text-primary-200',
  },
  '白白日记': {
    bg: 'bg-primary-50',
    text: 'text-primary-600',
    darkBg: 'dark:bg-primary-900/30',
    darkText: 'dark:text-primary-300',
  },
  '科普百科': {
    bg: 'bg-primary-100',
    text: 'text-primary-700',
    darkBg: 'dark:bg-primary-900/40',
    darkText: 'dark:text-primary-300',
  },
  '其他': {
    bg: 'bg-gray-100',
    text: 'text-gray-700',
    darkBg: '',
    darkText: '',
  },
}

const DEFAULT_COLOR: CategoryColor = {
  bg: 'bg-gray-100',
  text: 'text-gray-700',
  darkBg: '',
  darkText: '',
}

/**
 * Get Tailwind classes for a category badge.
 * Uses primary-* CSS variables so colors adapt to the user's theme hue.
 */
export function getCategoryColor(categoryName: string): string {
  const c = CATEGORY_COLORS[categoryName] ?? DEFAULT_COLOR
  return `${c.bg} ${c.text} ${c.darkBg} ${c.darkText}`
}

/**
 * Get just the background + text classes (no dark mode).
 */
export function getCategoryColorClasses(categoryName: string): CategoryColor {
  return CATEGORY_COLORS[categoryName] ?? DEFAULT_COLOR
}

/**
 * Medical scoring semantic colors (green→yellow→orange→red).
 * These are intentionally NOT tied to the theme hue because they
 * carry universal semantic meaning across cultures.
 */
export const SCORE_COLORS = {
  mild: 'text-green-600 dark:text-green-400',
  moderate: 'text-amber-600 dark:text-amber-400',
  severe: 'text-orange-600 dark:text-orange-400',
  critical: 'text-red-600 dark:text-red-400',
} as const
