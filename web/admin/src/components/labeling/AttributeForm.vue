<template>
  <form class="attr-form" @submit.prevent>
    <label class="field">身体部位
      <n-select :value="model.body_site" size="small" clearable filterable placeholder="未填写（用日记里选的部位）"
        :options="siteOptions" @update:value="set('body_site', $event)" />
    </label>
    <div class="row">
      <label class="field">拍摄类型
        <n-select :value="model.shot_type" size="small" :options="opts(SHOT)" @update:value="set('shot_type', $event)" />
      </label>
      <label class="field">光线
        <n-select :value="model.lighting" size="small" :options="opts(LIGHT)" @update:value="set('lighting', $event)" />
      </label>
    </div>
    <label class="field">成像方式
      <n-select :value="model.imaging" size="small" :options="opts(IMAGING)" @update:value="set('imaging', $event)" />
    </label>
    <fieldset class="field">
      <legend>Monk 肤色（以未受病灶影响的正常皮肤为准）</legend>
      <div class="tones">
        <button v-for="n in 10" :key="n" type="button" class="tone" :class="{ active: model.monk_skin_tone === n }"
          :style="{ background: MONK[n - 1] }" :aria-label="`Monk ${n}`" @click="set('monk_skin_tone', n)">{{ n }}</button>
        <button type="button" class="tone unsure" :class="{ active: model.monk_skin_tone === null }" @click="set('monk_skin_tone', null)">不确定</button>
      </div>
    </fieldset>
    <fieldset class="field">
      <legend>局部质量问题（仍可标注；整张不可用请点「不可用」）</legend>
      <n-checkbox-group :value="model.quality_issues" @update:value="set('quality_issues', $event as string[])">
        <div class="checks"><n-checkbox v-for="q in choices.quality_issues" :key="q" :value="q" :label="REASON_LABEL[q] ?? q" /></div>
      </n-checkbox-group>
    </fieldset>
    <fieldset class="field">
      <legend>可见体征（只记照片里看到的，不代表诊断）</legend>
      <div v-for="s in choices.signs" :key="s" class="sign">
        <span>{{ SIGN_LABEL[s] ?? s }}</span>
        <n-radio-group :value="model.signs[s] ?? 'unknown'" size="small" @update:value="setSign(s, $event)">
          <n-radio-button value="yes">有</n-radio-button>
          <n-radio-button value="no">无</n-radio-button>
          <n-radio-button value="unknown">无法判断</n-radio-button>
        </n-radio-group>
      </div>
    </fieldset>
    <label class="escalate"><n-checkbox :checked="model.escalate" @update:checked="set('escalate', $event)" /> 升级给医生（疑似非白癜风、炎症、儿童等）</label>
    <label class="field">备注（只写看到的）
      <n-input :value="model.notes" type="textarea" size="small" maxlength="500" show-count :autosize="{ minRows: 2, maxRows: 4 }" placeholder="例如：鼻翼阴影处看不清边界"
        @update:value="set('notes', $event)" />
    </label>
    <p class="hint">分型、分期、稳定性、临床评分只能由医生判断，标注员不填写。指南版本 {{ choices.guideline_version }}。</p>
  </form>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { REASON_LABEL, type LabelAttributes, type LabelingChoices, type Tristate } from '@/types/labeling'

const props = defineProps<{ attributes: LabelAttributes; choices: LabelingChoices }>()
const emit = defineEmits<{ (e: 'update:attributes', v: LabelAttributes): void }>()
const model = computed(() => props.attributes)

const SHOT: Record<string, string> = { overall: '整体', medium: '中景', close: '近景', unknown: '不确定' }
const LIGHT: Record<string, string> = { indoor: '室内', outdoor: '室外自然光', flash: '闪光灯', mixed: '混合', unknown: '不确定' }
const IMAGING: Record<string, string> = { rgb_phone: '手机 RGB', wood_lamp: '伍德灯', dermoscopy: '皮肤镜', unknown: '不确定' }
const SIGN_LABEL: Record<string, string> = {
  confetti: '彩纸屑样小白点', hypochromic_border: '边缘低色/多色', inflammatory_border: '边缘发红',
  leukotrichia: '毛发变白', linear: '线状/带状分布', cosmetic_or_sunburn: '遮盖/晒伤/化妆',
}
const MONK = ['#f6ede4', '#f3e7db', '#f7ead0', '#eadaba', '#d7bd96', '#a07e56', '#825c43', '#604134', '#3a312a', '#292420']

const siteOptions = computed(() => {
  const groups = props.choices.body_sites.groups
  return props.choices.body_sites.sites.filter((s) => !s.legacy || s.code === props.attributes.body_site)
    .map((s) => ({ label: `${s.label}（${groups[s.group] ?? s.group}）`, value: s.code }))
})
function opts(map: Record<string, string>) { return Object.entries(map).map(([value, label]) => ({ value, label })) }
function set<K extends keyof LabelAttributes>(key: K, value: LabelAttributes[K]) { emit('update:attributes', { ...props.attributes, [key]: value }) }
function setSign(key: string, value: Tristate) { set('signs', { ...props.attributes.signs, [key]: value }) }
</script>

<style scoped>
.attr-form { display: grid; gap: 12px; font-size: 12px; color: #cbd5e1; }
.field { display: grid; gap: 6px; border: 0; padding: 0; margin: 0; min-width: 0; }
legend { padding: 0; margin-bottom: 6px; color: #cbd5e1; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.tones { display: flex; flex-wrap: wrap; gap: 4px; }
.tone { width: 30px; height: 30px; border-radius: 6px; border: 2px solid transparent; cursor: pointer; font-size: 11px; color: #0f172a; font-variant-numeric: tabular-nums; }
.tone:nth-child(n + 6) { color: #f8fafc; }
.tone.active { border-color: #14b8a6; box-shadow: 0 0 0 2px rgba(20, 184, 166, .35); }
.tone.unsure { width: auto; padding: 0 8px; background: #1f2937; color: #cbd5e1; }
.checks { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.sign { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 4px 0; flex-wrap: wrap; }
.escalate { display: flex; align-items: center; gap: 8px; }
.hint { color: #64748b; margin: 0; line-height: 1.6; }
</style>
