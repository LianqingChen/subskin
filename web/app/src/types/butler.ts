/** Type compatibility for retained legacy modules; does not enable the retired UI. */
export type ButlerMascot = 'real' | 'deer'
export type ButlerStyle = 'circle' | 'rounded'
export type ButlerSize = 'small' | 'medium' | 'large'
export type ButlerPosition = 'left' | 'right'
export interface ButlerPreference {
  mascot: ButlerMascot
  style: ButlerStyle
  size: ButlerSize
  position: ButlerPosition
  greeting: string
  enabled: boolean
}
