/** Completion is distinct from request creation; old reports keep honest fallback labels. */
export function reportTime(value: { generated_at?: string | null; created_at?: string | null }): string {
  const raw = value.generated_at || value.created_at
  if (!raw) return '时间未记录'
  const date = new Date(raw)
  if (!Number.isFinite(date.getTime())) return '时间未记录'
  return `${value.generated_at ? '生成于' : '创建于'} ${date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  })}`
}
