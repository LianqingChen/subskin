import apiClient from './client'
import type { StoryTheme } from '@/utils/assessment-story/content'
export interface GeneratedStory { theme: StoryTheme; title: string; source: 'ai'; revision: string }
export async function generateAssessmentStory(id: number, revision: string, signal: AbortSignal, theme?: StoryTheme): Promise<GeneratedStory> {
  const { data } = await apiClient.post<GeneratedStory>(`/vasi/assess/${id}/story`, { revision, theme }, { signal, timeout: 45000 })
  if ((theme && data.theme !== theme) || data.source !== 'ai' || data.revision !== revision || !['sky', 'island', 'stars'].includes(data.theme) || typeof data.title !== 'string' || !data.title.trim() || data.title.length > 24) throw new Error('创意内容暂不可用，请重试')
  return data
}

export interface GeneratedArtwork { status: 'pending' | 'ready' | 'failed'; revision: string; model: string; theme?: StoryTheme; image_data_url?: string }
function pause(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Aborted', 'AbortError')); return }
    const done = () => { signal.removeEventListener('abort', cancel); resolve() }
    const timer = setTimeout(done, 2500)
    const cancel = () => { clearTimeout(timer); signal.removeEventListener('abort', cancel); reject(new DOMException('Aborted', 'AbortError')) }
    signal.addEventListener('abort', cancel, { once: true })
  })
}
export async function generateAssessmentArtwork(id: number, revision: string, signal: AbortSignal, retry = false, theme?: StoryTheme): Promise<string> {
  const path = `/vasi/assess/${id}/story/art`
  let state = (await apiClient.post<GeneratedArtwork>(path, { revision, retry, theme }, { signal, timeout: 40000 })).data
  const deadline = Date.now() + 600000
  while (true) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    if (state.revision !== revision || (theme && state.theme !== theme)) throw new Error('创意版本已更新')
    if (state.status === 'ready') {
      if (!state.image_data_url?.startsWith('data:image/jpeg;base64,') || state.image_data_url.length > 1500000) throw new Error('艺术图片暂不可用')
      return state.image_data_url
    }
    if (state.status !== 'pending' || Date.now() > deadline) throw new Error('艺术画面暂未生成')
    await pause(signal)
    state = (await apiClient.get<GeneratedArtwork>(path, { params: { revision, theme }, signal, timeout: 45000 })).data
  }
}
