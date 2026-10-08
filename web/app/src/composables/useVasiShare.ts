import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useDrafts } from '@/composables/useDrafts'
import { communityApi } from '@/api/community'
import type { useVasiAssess } from './useVasiAssess'

type VasiAssess = ReturnType<typeof useVasiAssess>

/**
 * useVasiShare — 评估结果发布到发现
 *
 * 组合标注图（原图 + AI 皮肤/白斑层）与原始照片 → 生成病情日记草稿 → 跳转发布页。
 */
export function useVasiShare(assess: VasiAssess) {
  const router = useRouter()
  const toast = useToast()
  const { saveDraftWithSync } = useDrafts()

  function composeAnnotatedImage(imageUrl: string, skinLayerUrl: string, lesionLayerUrl: string): Promise<string | null> {
    return new Promise((resolve) => {
      const loadImage = (src: string) => new Promise<HTMLImageElement>((res, rej) => {
        const img = new Image()
        img.onload = () => res(img)
        img.onerror = rej
        img.src = src
      })
      Promise.all([loadImage(imageUrl), loadImage(skinLayerUrl), loadImage(lesionLayerUrl)])
        .then(([baseImg, skinImg, lesionImg]) => {
          const w = skinImg.width || baseImg.naturalWidth
          const h = skinImg.height || baseImg.naturalHeight
          const canvas = document.createElement('canvas')
          canvas.width = w
          canvas.height = h
          const ctx = canvas.getContext('2d')
          if (!ctx) return resolve(null)
          ctx.drawImage(baseImg, 0, 0, w, h)
          ctx.globalAlpha = 0.55
          ctx.drawImage(skinImg, 0, 0, w, h)
          ctx.drawImage(lesionImg, 0, 0, w, h)
          ctx.globalAlpha = 1
          resolve(canvas.toDataURL('image/png'))
        })
        .catch(() => resolve(null))
    })
  }

  function dataUrlToFile(dataUrl: string, filename = 'annotated.png'): File {
    const [meta, base64] = dataUrl.split(',')
    const mime = meta.match(/:(.*?);/)?.[1] || 'image/png'
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    return new File([bytes], filename, { type: mime })
  }

  async function uploadAnnotatedImage(dataUrl: string): Promise<string | null> {
    try {
      const file = dataUrlToFile(dataUrl)
      const res = await communityApi.uploadImage(file)
      return res.image_url
    } catch (e) {
      console.error('Failed to upload annotated image:', e)
      return null
    }
  }

  async function shareResult() {
    const a = assess.lastAssessment.value
    if (!a) return
    const today = new Date().toISOString().split('T')[0]
    const htmlContent =
      `<p>今天记录了白斑照片：</p>` +
      `<ul>` +
      `<li>评估部位：${a.bodySite}</li>` +
      `<li>照片内白斑占比：${a.measurement?.area_percentage != null ? a.measurement.area_percentage + '%' : '此次无法量化'}</li>` +
      `<li>仅描述照片可见范围，不代表诊断或病情阶段</li>` +
      `</ul>` +
      `<p></p><p>今日感受：</p>`

    // 1st cover: 标注图（原图 + AI 皮肤/白斑层）；2nd cover: 原始照片。
    // 必须先把 dataURL 上传到服务器得到真实 URL（localStorage 与 API 均拒绝原始 base64）。
    const images: string[] = []
    if (assess.annotatedImage.value) {
      const uploadedUrl = await uploadAnnotatedImage(assess.annotatedImage.value)
      if (uploadedUrl) images.push(uploadedUrl)
    }
    if (a.imageUrl) images.push(a.imageUrl)
    const draftKey = await saveDraftWithSync({
      type: 'image',
      title: `${today} 病情日记`,
      content: htmlContent,
      images,
      categoryId: null,
      mood: '坚持中',
      isPrivate: true,
    })
    toast.success('已生成草稿')
    router.push({ path: '/community/new', query: { type: 'image', draftKey } })
  }

  return { composeAnnotatedImage, shareResult }
}
