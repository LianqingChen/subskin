/**
 * 发布确认弹窗（Promise 封装）— 公开帖发布前的隐私确认。
 *
 * 行为：
 * - 私密帖（isPrivate=true）直接放行（不公开、不外送，无需确认）；
 * - 公开帖弹出 PublishConfirmDialog：
 *   - 展示"将对所有用户可见"提示；
 *   - 检测到手机号/邮箱/身份证时提示将自动脱敏，用户可勾选保留原文；
 *   - 用户取消 → resolve(null)，调用方终止发布。
 */
import { createApp, h, reactive } from 'vue'
import PublishConfirmDialog from './PublishConfirmDialog.vue'
import { detectPii } from '@/utils/piiCheck'

export interface PublishDecision {
  confirmPii: boolean
  publicAck: boolean
}

export function confirmPublish(options: {
  title: string
  content: string
  isPrivate?: boolean
  preview?: { title: string; summary: string; images: string[] }
}): Promise<PublishDecision | null> {
  if (options.isPrivate) return Promise.resolve({ confirmPii: false, publicAck: false })

  return new Promise((resolve) => {
    const piiLabels = detectPii(`${options.title || ''}\n${options.content || ''}`)
    const state = reactive({ visible: true })
    const container = document.createElement('div')
    document.body.appendChild(container)

    const finish = (result: PublishDecision | null) => {
      state.visible = false
      app.unmount()
      container.remove()
      resolve(result)
    }

    const app = createApp({
      setup() {
        return () =>
          state.visible
            ? h(PublishConfirmDialog, {
                piiLabels,
                preview: options.preview,
                onCancel: () => finish(null),
                onConfirm: (payload: { confirmPii: boolean }) =>
                  finish({ confirmPii: payload.confirmPii, publicAck: true }),
              })
            : null
      },
    })
    app.mount(container)
  })
}
