import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { errorText } from '@/api/labeling'
import * as api from '@/api/training'
import type { Run, TrainingStatus } from '@/types/training'

const ACTIVE = ['queued', 'training', 'evaluating']

export function useRgbTraining() {
  const message = useMessage()
  const status = ref<TrainingStatus | null>(null)
  const exporting = ref(false)
  const busyRun = ref<string | null>(null)
  const epochs = ref(30)
  let timer: ReturnType<typeof setInterval> | null = null
  let disposed = false

  const running = computed(() => status.value?.runs.some((r) => ACTIVE.includes(r.state)) ?? false)

  async function load() {
    try {
      const result = await api.fetchTrainingStatus()
      if (!disposed) status.value = result
    } catch (cause) { message.error(errorText(cause, '加载分割模型状态失败')) }
  }

  async function act(action: () => Promise<void>, fallback: string, success?: string): Promise<boolean> {
    try {
      await action()
      if (success) message.success(success)
      await load()
      return true
    } catch (cause) {
      message.error(errorText(cause, fallback))
      return false
    }
  }

  async function exportDataset() {
    exporting.value = true
    try {
      const data = await api.exportDataset()
      if (data.valid) message.success(`已导出 ${data.items} 张、${data.subjects} 位用户`)
      else message.warning(`已导出，但未通过校验：${data.error}`)
      await load()
    } catch (cause) { message.error(errorText(cause, '导出失败')) } finally { exporting.value = false }
  }
  async function train(datasetId: string) {
    busyRun.value = datasetId
    await act(() => api.startRun(datasetId, epochs.value), '无法开始训练', '训练已在后台开始')
    busyRun.value = null
  }
  const cancel = (runId: string) => act(() => api.cancelRun(runId), '停止失败', '已请求停止')
  const register = (run: Run) => act(() => api.registerRun(run.run_id), '登记失败', '已登记，新任务立即生效')
  const disable = () => act(api.disableRegistry, '停用失败', '已停用')

  onMounted(() => {
    void load()
    timer = setInterval(() => { if (running.value) void load() }, 5000)
  })
  onBeforeUnmount(() => { disposed = true; if (timer) clearInterval(timer) })
  return { status, exporting, busyRun, epochs, running, load, exportDataset, train, cancel, register, disable }
}
