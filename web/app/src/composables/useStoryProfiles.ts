import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { patientProfileApi } from '@/api/patient-profile'
import { useAuthStore } from '@/stores/auth'
import { profileAge, type StoryPerson } from '@/utils/assessment-story/content'
export function useStoryProfiles() {
  const auth = useAuthStore()
  const options = ref<{ id: number; label: string; person: StoryPerson }[]>([])
  const selected = ref(0), error = ref(''), loading = ref(false)
  let generation = 0
  async function load() {
    const current = ++generation
    options.value = []; selected.value = 0; error.value = ''
    if (!auth.isLoggedIn) return
    loading.value = true
    try {
      const profiles = await patientProfileApi.list()
      if (current !== generation) return
      options.value = profiles.map((p, index) => {
        const age = profileAge(p.birth_date)
        const ageLabel = age == null ? '年龄未填写' : age < 18 ? '未成年' : age >= 60 ? '长者' : '成年'
        const relationship = p.is_self ? '本人' : p.relationship || '其他'
        return { id: p.id, label: `${relationship}档案 ${index + 1} · ${p.gender || '性别未填写'} · ${ageLabel}`, person: { age, gender: p.gender, relationship } }
      })
    } catch { if (current === generation) error.value = '档案暂时无法读取，仍可根据轮廓与部位创作。' }
    finally { if (current === generation) loading.value = false }
  }
  // Never assume the signed-in person is the subject of a family member's photo.
  watch(() => auth.user?.id, () => { void load() }, { immediate: true })
  onBeforeUnmount(() => { generation++ })
  const person = computed(() => options.value.find(p => p.id === selected.value)?.person || null)
  return { options, selected, person, error, loading, load }
}
