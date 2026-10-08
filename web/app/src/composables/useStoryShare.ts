import { onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { isAxiosError } from 'axios'
import { communityApi } from '@/api/community'
import { confirmPublish } from '@/components/community/Editor/publishConfirm'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import type { AssessmentResult } from '@/types/assessment'
import { STORY_URL } from '@/utils/assessment-story/content'
import { journalSummary } from '@/utils/assessment-story/summary'
import { journalShareImages } from '@/utils/assessment-story/share-images'
function escapeHtml(value: string) { return value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] || c) }
export function useStoryShare() {
  const busy = ref(false), toast = useToast(), router = useRouter(), auth = useAuthStore()
  let disposed = false
  const outcomes = new Map<string, number | 'pending'>()
  onBeforeUnmount(() => { disposed = true })
  function download(url: string) {
    const a = document.createElement('a'); a.href = url; a.download = 'SubSkin-我的轮廓故事.png'; a.click()
    toast.success('已发起保存；也可长按图片保存')
  }
  async function systemShare(blob: Blob, title: string, url: string) {
    const file = new File([blob], 'SubSkin-我的轮廓故事.png', { type: 'image/png' })
    if (!navigator.canShare?.({ files: [file] }) || !navigator.share) { download(url); return }
    try { await navigator.share({ files: [file], title, text: title, url: STORY_URL }) }
    catch (error) { if (!(error instanceof Error && error.name === 'AbortError')) toast.error('分享未完成，可改用保存图片') }
  }
  async function community(result: AssessmentResult, skin: string, lesion: string, poster: Blob | null, title: string, stillCurrent: () => boolean) {
    if (busy.value) return
    if (!auth.isLoggedIn) { auth.showLoginModal = true; return }
    const summary = journalSummary(result), owner = auth.user?.id
    if (!poster) { toast.warning('创意图尚未准备好，请稍后分享'); return }
    if (!summary.reviewed || !result.imageUrl) { toast.warning('请先核对并保存照片范围'); return }
    const current = () => !disposed && auth.isLoggedIn && owner === auth.user?.id && stillCurrent()
    busy.value = true
    let posterHash: string
    try { posterHash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await poster.arrayBuffer())), n => n.toString(16).padStart(2, '0')).join('') }
    catch { busy.value = false; toast.error('分享图片尚未准备好，请重试'); return }
    if (!current()) { busy.value = false; return }
    const key = `subskin-story-publish-v2:${owner}:${result.id}:${summary.revision}:${posterHash}`
    const remember = (value: number | 'pending' | null) => {
      if (value === null) outcomes.delete(key); else outcomes.set(key, value)
      try { if (value === null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, String(value)) } catch { /* In-memory guard remains active when browser storage is unavailable. */ }
    }
    let previous: string | number | undefined = outcomes.get(key)
    try { previous = previous ?? sessionStorage.getItem(key) ?? undefined } catch { /* Use the in-memory outcome. */ }
    if (previous === 'pending') { busy.value = false; toast.warning('发布状态尚未确认，请先到个人中心查看我的发布，避免重复发布'); return }
    if (previous && Number(previous) > 0) { busy.value = false; await router.push(`/community/${Number(previous)}`); return }
    busy.value = true
    const previews: string[] = []
    try {
      const images = await journalShareImages(result.imageUrl, skin, lesion, poster)
      if (!current()) return
      images.forEach(image => previews.push(URL.createObjectURL(image)))
      const heading = title || `${summary.site}的照片记录`
      const content = `<p>${escapeHtml(heading)}</p><p>本次白斑记录</p><p>${summary.dataLines.map(escapeHtml).join('<br>')}</p><p>仅限本张照片中的可见皮肤，不构成医疗建议。</p>`
      const decision = await confirmPublish({ title: heading, content, preview: { title: heading, summary: summary.dataLines.join('；'), images: previews } })
      if (!decision || !current()) return
      const categories = await communityApi.getCategories()
      if (!current()) return
      const category = categories.find(item => /日常|记录|生活/.test(item.name)) || categories[0]
      if (!category) throw new Error('暂无可用分类')
      const urls: string[] = []
      for (let i = 0; i < images.length; i++) {
        const upload = await communityApi.uploadImage(new File([images[i]], `subskin-journal-${i}.png`, { type: 'image/png' }))
        if (!current()) return
        if (!upload.image_url) throw new Error('图片上传未完成')
        urls.push(upload.image_url)
      }
      remember('pending')
      try {
        const post = await communityApi.createPost({ title: heading, content, post_type: 'image', category_id: category.id,
          images: urls, image_metas: urls.map((image_url, index) => ({ image_url, ...(index === 2 ? { body_site: result.bodySite, capture_date: summary.date || undefined } : {}) })),
          is_private: false, is_anonymous: true, public_ack: decision.publicAck, confirm_pii: decision.confirmPii })
        remember(post.id)
        if (current()) { toast.success('已将创意与照片记录一起发布'); await router.push(`/community/${post.id}`) }
      } catch (e) {
        if (isAxiosError(e) && e.response && e.response.status < 500) remember(null)
        throw e
      }
    } catch {
      if (current()) toast.error(outcomes.get(key) === 'pending' ? '发布状态尚未确认，请到个人中心查看我的发布' : '分享未完成，请重试；照片记录已保留')
    } finally { previews.forEach(URL.revokeObjectURL); busy.value = false }
  }
  return { busy, download, systemShare, community }
}
