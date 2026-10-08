export interface MoodMeta {
  icon: string
  label: string
  color: string
}

// 键同时覆盖纯文字新值与存量 emoji 前缀旧值，保证历史帖子渲染一致
const MOOD_META: Record<string, MoodMeta> = {
  坚持中: { icon: 'ri-boxing-line', label: '坚持中', color: 'bg-orange-500/80 text-white' },
  低落: { icon: 'ri-emotion-sad-line', label: '低落', color: 'bg-purple-500/80 text-white' },
  好转: { icon: 'ri-emotion-happy-line', label: '好转', color: 'bg-green-500/80 text-white' },
  疑问: { icon: 'ri-question-line', label: '疑问', color: 'bg-cyan-500/80 text-white' },
  '💪坚持中': { icon: 'ri-boxing-line', label: '坚持中', color: 'bg-orange-500/80 text-white' },
  '😔低落': { icon: 'ri-emotion-sad-line', label: '低落', color: 'bg-purple-500/80 text-white' },
  '🎉好转': { icon: 'ri-emotion-happy-line', label: '好转', color: 'bg-green-500/80 text-white' },
  '🤔疑问': { icon: 'ri-question-line', label: '疑问', color: 'bg-cyan-500/80 text-white' },
}

export function getMoodMeta(mood: string | null | undefined): MoodMeta | null {
  if (!mood) return null
  return MOOD_META[mood] ?? null
}

export function moodLabel(mood: string | null | undefined): string {
  return getMoodMeta(mood)?.label ?? mood ?? ''
}

export function normalizeMoodValue(mood: string | null | undefined): string {
  return getMoodMeta(mood)?.label ?? mood ?? ''
}
