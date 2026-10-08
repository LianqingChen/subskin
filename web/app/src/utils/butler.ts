import type { ButlerSize, ButlerStyle } from '@/types'

/**
 * 小白管家外观尺寸/样式映射。
 * 形象（mascot）目前仅金斑蝶（real）与梅花鹿（deer），由 ButlerCreature3D 程序化 3D 渲染；
 * WebGL 不可用时内部回退 SVG 卡通形象（ButlerMascot），不在此表。
 */
export const BUTLER_SIZE_PX: Record<ButlerSize, number> = {
  small: 44,
  medium: 56,
  large: 64,
}

export const BUTLER_STYLE_CLASS: Record<ButlerStyle, string> = {
  circle: 'rounded-full',
  rounded: 'rounded-2xl',
}

export const BUTLER_ACCEPT_TYPES = '.jpg,.jpeg,.png,.webp,.pdf,.doc,.docx,.txt,.md'
