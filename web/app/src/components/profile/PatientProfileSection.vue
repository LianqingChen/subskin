<script setup lang="ts">
/**
 * PatientProfileSection — 白友档案管理（列表 + 新增/编辑弹窗 + 默认档案选择）
 * 从 ProfilePage.vue 拆分而来
 */
import { computed, reactive, ref, watch } from 'vue'
import { patientProfileApi, type PatientProfile, type ModuleDefaults } from '@/api/patient-profile'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  profiles: PatientProfile[]
  moduleDefaults: ModuleDefaults
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'save-defaults', defaults: ModuleDefaults): void
}>()

const toast = useToast()

const CURRENT_YEAR = new Date().getFullYear()
const YEAR_OPTIONS = Array.from({ length: CURRENT_YEAR - 1919 }, (_, i) => CURRENT_YEAR - i)
const MONTH_OPTIONS = Array.from({ length: 12 }, (_, i) => i + 1)

const showFormModal = ref(false)
const isSaving = ref(false)
const editingProfile = ref<PatientProfile | null>(null)

const form = reactive({ name: '', relationship: '本人', gender: '', birth_date: '', diagnosis_date: '', vitiligo_type: '', notes: '' })
const birthDateParts = reactive({ year: '' as string | number, month: '' as string | number, day: '' as string | number })
const diagnosisDateParts = reactive({ year: '' as string | number, month: '' as string | number, day: '' as string | number })

function getDaysInMonth(year: string | number, month: string | number): number {
  const y = Number(year)
  const m = Number(month)
  if (!y || !m) return 31
  return new Date(y, m, 0).getDate()
}

const birthDayOptions = computed(() => {
  const days = getDaysInMonth(birthDateParts.year, birthDateParts.month)
  return Array.from({ length: days }, (_, i) => i + 1)
})

const diagnosisDayOptions = computed(() => {
  const days = getDaysInMonth(diagnosisDateParts.year, diagnosisDateParts.month)
  return Array.from({ length: days }, (_, i) => i + 1)
})

function datePartsToString(parts: { year: string | number; month: string | number; day: string | number }): string {
  const y = Number(parts.year)
  const m = Number(parts.month)
  const d = Number(parts.day)
  if (!y || !m || !d) return ''
  return `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function stringToDateParts(dateStr: string): { year: string | number; month: string | number; day: string | number } {
  if (!dateStr) return { year: '', month: '', day: '' }
  const [y, m, d] = dateStr.split('-').map(Number)
  return { year: y || '', month: m || '', day: d || '' }
}

watch([() => birthDateParts.year, () => birthDateParts.month, () => birthDateParts.day], () => {
  const newVal = datePartsToString(birthDateParts)
  if (newVal !== form.birth_date) form.birth_date = newVal
  const maxDay = getDaysInMonth(birthDateParts.year, birthDateParts.month)
  if (Number(birthDateParts.day) > maxDay) birthDateParts.day = maxDay
})

watch([() => diagnosisDateParts.year, () => diagnosisDateParts.month, () => diagnosisDateParts.day], () => {
  const newVal = datePartsToString(diagnosisDateParts)
  if (newVal !== form.diagnosis_date) form.diagnosis_date = newVal
  const maxDay = getDaysInMonth(diagnosisDateParts.year, diagnosisDateParts.month)
  if (Number(diagnosisDateParts.day) > maxDay) diagnosisDateParts.day = maxDay
})

function openAdd() {
  editingProfile.value = null
  Object.assign(form, { name: '', relationship: '本人', gender: '', birth_date: '', diagnosis_date: '', vitiligo_type: '', notes: '' })
  Object.assign(birthDateParts, { year: '', month: '', day: '' })
  Object.assign(diagnosisDateParts, { year: '', month: '', day: '' })
  showFormModal.value = true
}

function openEdit(profile: PatientProfile) {
  editingProfile.value = profile
  Object.assign(form, {
    name: profile.name,
    relationship: profile.relationship,
    gender: profile.gender || '',
    birth_date: profile.birth_date || '',
    diagnosis_date: profile.diagnosis_date || '',
    vitiligo_type: profile.vitiligo_type || '',
    notes: profile.notes || ''
  })
  Object.assign(birthDateParts, stringToDateParts(profile.birth_date || ''))
  Object.assign(diagnosisDateParts, stringToDateParts(profile.diagnosis_date || ''))
  showFormModal.value = true
}

async function save() {
  if (!form.name.trim()) {
    toast.warning('请输入姓名')
    return
  }
  if (!form.relationship) {
    toast.warning('请选择与白友关系')
    return
  }

  isSaving.value = true
  try {
    const data = {
      name: form.name.trim(),
      relationship: form.relationship,
      gender: form.gender || null,
      birth_date: form.birth_date || null,
      diagnosis_date: form.diagnosis_date || null,
      vitiligo_type: form.vitiligo_type || null,
      notes: form.notes || null
    }

    if (editingProfile.value) {
      await patientProfileApi.update(editingProfile.value.id, data)
      toast.success('白友档案已更新')
    } else {
      await patientProfileApi.create(data)
      toast.success('白友档案已添加')
    }
    showFormModal.value = false
    emit('refresh')
  } catch (error: any) {
    toast.error(error.response?.data?.detail || '保存失败，请稍后重试')
  } finally {
    isSaving.value = false
  }
}

async function deleteProfile(profile: PatientProfile) {
  if (!confirm(`确定要删除白友档案 "${profile.name}" 吗？`)) return
  try {
    await patientProfileApi.delete(profile.id)
    toast.success('白友档案已删除')
    emit('refresh')
  } catch (error: any) {
    toast.error(error.response?.data?.detail || '删除失败，请稍后重试')
  }
}

function onDefaultsChange() {
  emit('save-defaults', { ...props.moduleDefaults })
}
</script>

<template>
  <div class="card p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-medium text-gray-900"><i class="ri-team-line"></i> 白友档案</h3>
      <button class="btn-ghost text-sm" @click="openAdd">+ 添加</button>
    </div>

    <!-- Profile list -->
    <div v-if="profiles.length === 0" class="text-sm text-gray-400 text-center py-4">暂无档案</div>
    <div v-else class="space-y-2">
      <div v-for="profile in profiles" :key="profile.id" class="flex items-center justify-between p-3 rounded-lg bg-gray-50">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-sm font-medium text-primary-700 dark:text-primary-300">
            {{ profile.name.charAt(0) }}
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-900">{{ profile.name }}</span>
              <span v-if="profile.is_self" class="text-xs bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300 px-1.5 py-0.5 rounded">本人</span>
              <span v-else class="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{{ profile.relationship }}</span>
            </div>
            <div class="text-xs text-gray-400 mt-0.5">
              <span v-if="profile.vitiligo_type">{{ profile.vitiligo_type }}</span>
              <span v-if="profile.diagnosis_date"> · 确诊 {{ profile.diagnosis_date }}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button class="text-gray-400 hover:text-primary-600" @click="openEdit(profile)"><i class="ri-edit-line"></i></button>
          <button v-if="!profile.is_self" class="text-gray-400 hover:text-red-500" @click="deleteProfile(profile)"><i class="ri-delete-bin-line"></i></button>
        </div>
      </div>
    </div>

    <!-- Module defaults -->
    <div v-if="profiles.length > 1" class="mt-4 pt-3 border-t border-gray-200 dark:border-gray-600">
      <h4 class="text-sm font-medium text-gray-700 mb-2">默认档案</h4>
      <div class="space-y-2">
        <div class="flex items-center justify-between text-sm">
          <span class="text-gray-600">测评</span>
          <select v-model="moduleDefaults.tracker_profile_id" class="text-sm border rounded px-2 py-1 bg-white" @change="onDefaultsChange">
            <option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
        <div class="flex items-center justify-between text-sm">
          <span class="text-gray-600">体检解读</span>
          <select v-model="moduleDefaults.report_profile_id" class="text-sm border rounded px-2 py-1 bg-white" @change="onDefaultsChange">
            <option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
        <div class="flex items-center justify-between text-sm">
          <span class="text-gray-600">白白日记</span>
          <select v-model="moduleDefaults.diary_profile_id" class="text-sm border rounded px-2 py-1 bg-white" @change="onDefaultsChange">
            <option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
      </div>
    </div>
  </div>

  <!-- Add/Edit Patient Profile Modal -->
  <Teleport to="body">
    <div
      v-if="showFormModal"
      class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center"
      @click.self="showFormModal = false"
    >
      <div class="bg-white w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4 max-h-[90dvh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-semibold text-gray-900">{{ editingProfile ? '编辑白友' : '添加白友' }}</h2>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="showFormModal = false">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">姓名 <span class="text-red-500">*</span></label>
            <input
              v-model="form.name"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900"
              placeholder="请输入姓名"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">与白友关系 <span class="text-red-500">*</span></label>
            <select
              v-model="form.relationship"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900 disabled:opacity-50"
              :disabled="editingProfile?.is_self"
            >
              <option value="本人">本人</option>
              <option value="父母">父母</option>
              <option value="孩子">孩子</option>
              <option value="伴侣">伴侣</option>
              <option value="朋友">朋友</option>
              <option value="其他">其他</option>
            </select>
          </div>

          <div class="grid gap-3 md:grid-cols-2">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">性别</label>
              <select v-model="form.gender" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900">
                <option value="">未设置</option>
                <option value="男">男</option>
                <option value="女">女</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">白癜风类型</label>
              <select v-model="form.vitiligo_type" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900">
                <option value="">未确定</option>
                <option value="寻常型">寻常型</option>
                <option value="节段型">节段型</option>
                <option value="混合型">混合型</option>
              </select>
            </div>
          </div>

          <div class="space-y-3">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">出生日期</label>
              <div class="grid grid-cols-3 gap-2">
                <select v-model="birthDateParts.year" class="w-full px-2 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900 text-sm">
                  <option value="">年</option>
                  <option v-for="y in YEAR_OPTIONS" :key="y" :value="y">{{ y }}</option>
                </select>
                <select v-model="birthDateParts.month" class="w-full px-2 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900 text-sm">
                  <option value="">月</option>
                  <option v-for="m in MONTH_OPTIONS" :key="m" :value="m">{{ m }}月</option>
                </select>
                <select v-model="birthDateParts.day" class="w-full px-2 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900 text-sm">
                  <option value="">日</option>
                  <option v-for="d in birthDayOptions" :key="d" :value="d">{{ d }}日</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">确诊日期</label>
              <div class="grid grid-cols-3 gap-2">
                <select v-model="diagnosisDateParts.year" class="w-full px-2 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900 text-sm">
                  <option value="">年</option>
                  <option v-for="y in YEAR_OPTIONS" :key="y" :value="y">{{ y }}</option>
                </select>
                <select v-model="diagnosisDateParts.month" class="w-full px-2 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900 text-sm">
                  <option value="">月</option>
                  <option v-for="m in MONTH_OPTIONS" :key="m" :value="m">{{ m }}月</option>
                </select>
                <select v-model="diagnosisDateParts.day" class="w-full px-2 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900 text-sm">
                  <option value="">日</option>
                  <option v-for="d in diagnosisDayOptions" :key="d" :value="d">{{ d }}日</option>
                </select>
              </div>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
            <textarea
              v-model="form.notes"
              rows="3"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900 resize-none"
              placeholder="添加一些备注信息..."
            ></textarea>
          </div>

          <div class="flex flex-wrap gap-2 pt-2">
            <button type="button" class="btn-primary" :disabled="isSaving" @click="save">
              {{ isSaving ? '保存中...' : '保存' }}
            </button>
            <button type="button" class="btn-ghost" :disabled="isSaving" @click="showFormModal = false">
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
