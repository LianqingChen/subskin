/**
 * SINGLE SOURCE OF TRUTH for body-site identifiers across the VASI assessment stack.
 * Consumers: DigitalHuman, BodyPartCamera, AssessmentSection, backend `body_site` field.
 * `bsaPercent` follows the modified VASI hand-unit system (Hamzavi et al. 2004).
 */

export type BodySite =
  | 'face'
  | 'neck'
  | 'chest'
  | 'abdomen'
  | 'upper_back'
  | 'lower_back'
  | 'left_arm'
  | 'right_arm'
  | 'left_hand'
  | 'right_hand'
  | 'left_leg'
  | 'right_leg'
  | 'left_foot'
  | 'right_foot'

export interface BodySiteMeta {
  id: BodySite
  label: string
  side: 'left' | 'right' | 'center'
  group: 'head' | 'torso' | 'arm' | 'hand' | 'leg' | 'foot'
  bsaPercent: number
  view: 'front' | 'back' | 'both'
}

export const BODY_SITES: Record<BodySite, BodySiteMeta> = {
  face:        { id: 'face',        label: '面部',   side: 'center', group: 'head',  bsaPercent: 4.5,  view: 'both' },
  neck:        { id: 'neck',        label: '颈部',   side: 'center', group: 'head',  bsaPercent: 1.0,  view: 'both' },
  chest:       { id: 'chest',       label: '胸部',   side: 'center', group: 'torso', bsaPercent: 9.0,  view: 'front' },
  abdomen:     { id: 'abdomen',     label: '腹部',   side: 'center', group: 'torso', bsaPercent: 9.0,  view: 'front' },
  upper_back:  { id: 'upper_back',  label: '上背部', side: 'center', group: 'torso', bsaPercent: 9.0,  view: 'back' },
  lower_back:  { id: 'lower_back',  label: '下背部', side: 'center', group: 'torso', bsaPercent: 9.0,  view: 'back' },
  left_arm:    { id: 'left_arm',    label: '左臂',   side: 'left',   group: 'arm',   bsaPercent: 4.5,  view: 'both' },
  right_arm:   { id: 'right_arm',   label: '右臂',   side: 'right',  group: 'arm',   bsaPercent: 4.5,  view: 'both' },
  left_hand:   { id: 'left_hand',   label: '左手',   side: 'left',   group: 'hand',  bsaPercent: 1.0,  view: 'both' },
  right_hand:  { id: 'right_hand',  label: '右手',   side: 'right',  group: 'hand',  bsaPercent: 1.0,  view: 'both' },
  left_leg:    { id: 'left_leg',    label: '左腿',   side: 'left',   group: 'leg',   bsaPercent: 9.0,  view: 'both' },
  right_leg:   { id: 'right_leg',   label: '右腿',   side: 'right',  group: 'leg',   bsaPercent: 9.0,  view: 'both' },
  left_foot:   { id: 'left_foot',   label: '左脚',   side: 'left',   group: 'foot',  bsaPercent: 1.75, view: 'both' },
  right_foot:  { id: 'right_foot',  label: '右脚',   side: 'right',  group: 'foot',  bsaPercent: 1.75, view: 'both' },
}

export const PART_LABELS: Record<string, string> = Object.fromEntries(
  Object.values(BODY_SITES).map(m => [m.id, m.label])
) as Record<BodySite, string>

export function isValidBodySite(value: unknown): value is BodySite {
  return typeof value === 'string' && value in BODY_SITES
}

export type CameraShapeKey =
  | 'face' | 'neck' | 'chest' | 'abdomen' | 'upper_back' | 'lower_back'
  | 'arm' | 'hand' | 'leg' | 'foot'

/**
 * Map a sided body-site to its camera-mask shape group.
 * `left_hand` and `right_hand` resolve to the same `hand` frame —
 * the side only affects history grouping, not the camera guide.
 */
export function getCameraShapeKey(site: string): CameraShapeKey {
  if (!isValidBodySite(site)) return 'face'
  switch (BODY_SITES[site].group) {
    case 'arm':  return 'arm'
    case 'hand': return 'hand'
    case 'leg':  return 'leg'
    case 'foot': return 'foot'
    case 'head':
      return site === 'face' ? 'face' : 'neck'
    case 'torso':
      if (site === 'chest') return 'chest'
      if (site === 'abdomen') return 'abdomen'
      if (site === 'upper_back') return 'upper_back'
      return 'lower_back'
  }
}

/** Resolve which side of the body this site belongs to (for crop hints). */
export function getBodySide(site: string): 'left' | 'right' | 'center' {
  return isValidBodySite(site) ? BODY_SITES[site].side : 'center'
}
