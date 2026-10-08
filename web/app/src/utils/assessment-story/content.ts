import { BODY_SITES, PART_LABELS, type BodySite } from '@/constants/bodySites'
import type { StoryShape } from './mask'
export type StoryTheme = 'sky' | 'island' | 'stars'
export type StoryFormat = 'portrait' | 'square' | 'full'
export interface StoryPerson { age: number | null; gender: string | null; relationship: string }
export const STORY_URL = 'https://subskin.cn/'
export const STORY_THEMES = [
  { id: 'sky' as const, label: '我的晴空', icon: 'ri-cloud-line' },
  { id: 'island' as const, label: '自己的海岸', icon: 'ri-water-flash-line' },
  { id: 'stars' as const, label: '微光成诗', icon: 'ri-sparkling-line' },
]
export function profileAge(birth: string | null, today = new Date()): number | null {
  if (!birth || !/^\d{4}-\d{2}-\d{2}$/.test(birth)) return null
  const [y, m, d] = birth.split('-').map(Number), date = new Date(y, m - 1, d)
  if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d) return null
  const age = today.getFullYear() - y - (today.getMonth() + 1 < m || (today.getMonth() + 1 === m && today.getDate() < d) ? 1 : 0)
  return age >= 0 && age <= 120 ? age : null
}
export function siteLabel(site: string): string { return PART_LABELS[site] || site || '本次照片' }
export function makeStory(shape: StoryShape, theme: StoryTheme, site: string, person: StoryPerson | null, variant: number) {
  const meta = BODY_SITES[site as BodySite] || Object.values(BODY_SITES).find(value => value.label === site)
  const group = meta?.group
  const many = shape.clusters > 1
  const objects = theme === 'sky' ? (many ? '一组云朵' : '一朵云') : theme === 'island' ? (many ? '一片群岛' : '一座小岛') : (many ? '一簇星光' : '一束微光')
  const geometry = { scattered: '散落的轮廓', vertical: '向上延伸的轮廓', horizontal: '横向舒展的轮廓', compact: '较为集中的轮廓' }[shape.kind]
  const captions = {
    sky: { compact: ['这一朵云，\n有自己的天空。', 'Every cloud has a sky of its own.'], scattered: ['散落的云，\n也能组成晴空。', 'Scattered clouds still share a sky.'], vertical: ['让这一朵云，\n向着天空舒展。', 'Let this cloud reach for the open sky.'], horizontal: ['天空很宽，\n容得下我的模样。', 'There is room for me in this wide sky.'] },
    island: { compact: ['自己的小岛，\n也有温暖的海岸。', 'My little island has a welcoming shore.'], scattered: ['每一座小岛，\n都被同一片海拥抱。', 'Every island is held by the same sea.'], vertical: ['沿着自己的海岸，\n慢慢向前。', 'Follow your own shore, at your own pace.'], horizontal: ['海岸的每道弯，\n都有自己的风景。', 'Every curve of the coast holds a view.'] },
    stars: { compact: ['这一束微光，\n也值得被看见。', 'This little light deserves to be seen.'], scattered: ['散落的微光，\n也能连成星河。', 'Little lights can become a galaxy.'], vertical: ['循着自己的光，\n一步一步向前。', 'Follow your light, one step at a time.'], horizontal: ['让点点微光，\n铺成自己的星河。', 'Let little lights become your own galaxy.'] },
  }
  let [title, english] = captions[theme][shape.kind]
  if (many && shape.kind === 'compact') [title, english] = theme === 'sky' ? ['相伴的云，\n也有自己的天空。', 'Clouds together have a sky of their own.'] : theme === 'island' ? ['相邻的小岛，\n各有自己的风景。', 'Nearby islands each hold their own view.'] : ['相聚的微光，\n一起照亮今天。', 'Little lights together brighten today.']
  if (variant % 2 === 1) {
    if (group === 'hand' || group === 'arm') [title, english] = theme === 'sky' ? ['把自己的天空，\n轻轻握在手心。', 'Hold a little sky in your hands.'] : theme === 'island' ? ['手心里的小岛，\n也能拥抱生活。', 'An island in my hands, a life to embrace.'] : ['手边的点点光，\n照亮平凡的今天。', 'Little lights at hand brighten today.']
    else if (group === 'leg' || group === 'foot') [title, english] = theme === 'sky' ? ['带着一片晴空，\n走自己的路。', 'Carry a little sky along your own path.'] : theme === 'island' ? ['沿着自己的海岸，\n走自己的路。', 'Walk your own path along your own shore.'] : ['脚下有微光，\n前路慢慢走。', 'A little light, one step at a time.']
    else if (group === 'head') [title, english] = theme === 'sky' ? ['云有不同形状，\n我有自己的模样。', 'Clouds have their shapes. I have my own.'] : theme === 'island' ? ['海岸无需笔直，\n我也自有模样。', 'Coasts can curve. I can be myself.'] : ['每一点光，\n都映出独特的我。', 'Every little light reflects a unique me.']
    else [title, english] = theme === 'sky' ? ['让这片云，\n陪我自在呼吸。', 'Let these clouds breathe with me.'] : theme === 'island' ? ['在自己的小岛，\n安心歇一歇。', 'Rest a while on your own little island.'] : ['把这片微光，\n留给今天的自己。', 'Keep this little light for yourself today.']
  }
  const age = person?.age
  const note = age != null && age < 18 ? '慢慢长大，也慢慢认识独一无二的自己。' : age != null && age >= 60 ? '走过许多风景，今天也有属于自己的从容。' : group === 'hand' || group === 'arm' ? '这双手，仍可以触碰生活里喜欢的事物。' : group === 'leg' || group === 'foot' ? '每一步，都可以按自己的节奏。' : group === 'head' ? '被看见时，也可以自在地做自己。' : '留一点空间，给今天真实的感受。'
  const dedication = person?.gender === '女' ? '写给她的一幅画' : person?.gender === '男' ? '写给他的一幅画' : person?.relationship && person.relationship !== '本人' ? '写给你的一幅画' : '写给今天的自己'
  return { title, english, note, dedication, objects,
    reason: `从${siteLabel(site)}本次确认的${geometry}出发，化作${objects}；保留各块形状、间距与相对位置。`,
    caption: `由我的轮廓，化作${objects}` }
}
