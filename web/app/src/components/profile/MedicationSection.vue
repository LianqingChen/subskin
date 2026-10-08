<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { medicationApi, type MedicationReminder } from '@/api/medication'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const reminders = ref<MedicationReminder[]>([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref<number | null>(null)

const form = ref({
  medication_name: '',
  dosage: '',
  frequency: 'daily',
  reminder_times: ['08:00'],
  notes: '',
})

const frequencyOptions = [
  { value: 'daily', label: '每天' },
  { value: 'twice_daily', label: '每天两次' },
  { value: 'weekly', label: '每周' },
  { value: 'custom', label: '自定义' },
]

onMounted(loadReminders)

async function loadReminders() {
  loading.value = true
  try {
    reminders.value = await medicationApi.getReminders()
  } catch {
    // silently fail — user may not be logged in
  } finally {
    loading.value = false
  }
}

function openAddForm() {
  editingId.value = null
  form.value = { medication_name: '', dosage: '', frequency: 'daily', reminder_times: ['08:00'], notes: '' }
  showForm.value = true
}

function openEditForm(r: MedicationReminder) {
  editingId.value = r.id
  form.value = {
    medication_name: r.medication_name,
    dosage: r.dosage || '',
    frequency: r.frequency,
    reminder_times: r.reminder_times || ['08:00'],
    notes: r.notes || '',
  }
  showForm.value = true
}

async function saveReminder() {
  if (!form.value.medication_name.trim()) {
    toast.show('请输入药品名称', 'warning')
    return
  }
  try {
    const payload = {
      medication_name: form.value.medication_name.trim(),
      dosage: form.value.dosage.trim() || undefined,
      frequency: form.value.frequency,
      reminder_times: form.value.reminder_times,
      notes: form.value.notes.trim() || undefined,
    }
    if (editingId.value) {
      await medicationApi.updateReminder(editingId.value, payload)
      toast.success('用药提醒已更新')
    } else {
      await medicationApi.createReminder(payload)
      toast.success('用药提醒已添加')
    }
    showForm.value = false
    await loadReminders()
  } catch {
    toast.error('保存失败，请重试')
  }
}

async function deleteReminder(id: number) {
  if (!confirm('确定删除这条用药提醒？')) return
  try {
    await medicationApi.deleteReminder(id)
    toast.success('已删除')
    await loadReminders()
  } catch {
    toast.error('删除失败')
  }
}

async function toggleActive(r: MedicationReminder) {
  try {
    await medicationApi.updateReminder(r.id, { is_active: !r.is_active })
    r.is_active = !r.is_active
  } catch {
    toast.error('操作失败')
  }
}

function freqLabel(freq: string) {
  return frequencyOptions.find(f => f.value === freq)?.label || freq
}
</script>

<template>
  <div class="card p-4">
    <div class="flex items-center justify-between gap-3 mb-3">
      <h3 class="font-medium text-gray-900"><i class="ri-capsule-line"></i> 用药提醒</h3>
      <button class="text-sm text-primary-600 hover:underline" @click="openAddForm">+ 添加</button>
    </div>

    <div v-if="loading" class="text-center py-4 text-xs text-gray-400">加载中...</div>

    <div v-else-if="!reminders.length" class="text-center py-4 text-xs text-gray-400">
      还没有用药提醒，添加后 AI 问答将引用你的用药数据
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="r in reminders"
        :key="r.id"
        class="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-gray-50 dark:bg-gray-800"
      >
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-900 truncate">
            {{ r.medication_name }}
            <span v-if="r.dosage" class="text-gray-500 font-normal">· {{ r.dosage }}</span>
          </p>
          <p class="text-xs text-gray-400">{{ freqLabel(r.frequency) }} · {{ r.reminder_times?.join('、') }}</p>
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <button
            class="w-7 h-7 rounded flex items-center justify-center text-gray-400 hover:text-primary-600 hover:bg-primary-50"
            @click="toggleActive(r)"
            :title="r.is_active ? '已启用' : '已暂停'"
          >
            <i :class="r.is_active ? 'ri-pause-mini-line' : 'ri-play-mini-line'" class="text-base"></i>
          </button>
          <button
            class="w-7 h-7 rounded flex items-center justify-center text-gray-400 hover:text-blue-600 hover:bg-blue-50"
            @click="openEditForm(r)"
            title="编辑"
          >
            <i class="ri-edit-line text-base"></i>
          </button>
          <button
            class="w-7 h-7 rounded flex items-center justify-center text-gray-400 hover:text-red-600 hover:bg-red-50"
            @click="deleteReminder(r.id)"
            title="删除"
          >
            <i class="ri-delete-bin-line text-base"></i>
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showForm" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50" @click.self="showForm = false">
        <div class="w-full sm:max-w-md bg-white rounded-t-2xl sm:rounded-2xl p-5 max-h-[85vh] overflow-y-auto">
          <h3 class="text-base font-semibold mb-4">{{ editingId ? '编辑用药提醒' : '添加用药提醒' }}</h3>
          <div class="space-y-3">
            <div>
              <label class="text-xs text-gray-500">药品名称 *</label>
              <input v-model="form.medication_name" placeholder="如：他克莫司软膏" class="input-base mt-1" />
            </div>
            <div>
              <label class="text-xs text-gray-500">剂量</label>
              <input v-model="form.dosage" placeholder="如：0.1% 每日两次" class="input-base mt-1" />
            </div>
            <div>
              <label class="text-xs text-gray-500">频率</label>
              <select v-model="form.frequency" class="input-base mt-1">
                <option v-for="opt in frequencyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-gray-500">提醒时间</label>
              <div class="flex flex-wrap gap-2 mt-1">
                <input
                  v-for="(_, i) in form.reminder_times"
                  :key="i"
                  v-model="form.reminder_times[i]"
                  type="time"
                  class="input-base w-28"
                />
                <button class="text-sm text-primary-600" @click="form.reminder_times.push('08:00')">+ 时间</button>
                <button v-if="form.reminder_times.length > 1" class="text-sm text-red-500" @click="form.reminder_times.pop()">- 时间</button>
              </div>
            </div>
            <div>
              <label class="text-xs text-gray-500">备注</label>
              <textarea v-model="form.notes" rows="2" placeholder="可选" class="input-base mt-1"></textarea>
            </div>
          </div>
          <div class="flex gap-3 mt-5">
            <button class="flex-1 btn-ghost py-2.5" @click="showForm = false">取消</button>
            <button class="flex-1 btn-primary py-2.5" @click="saveReminder">保存</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
