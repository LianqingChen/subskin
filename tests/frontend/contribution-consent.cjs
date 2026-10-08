const {test}=require('node:test')
const assert=require('node:assert/strict')
const {readFileSync}=require('node:fs')
const read=f=>readFileSync(f,'utf8')

const frontendVersion=()=>read('web/app/src/constants/contributionText.ts').match(/CONTRIBUTION_TEXT_VERSION\s*=\s*'([^']+)'/)[1]
const backendVersion=()=>read('web/backend/services/data_consent.py').match(/CURRENT_TEXT_VERSION\s*=\s*"([^"]+)"/)[1]

test('consent text version is identical on frontend and backend',()=>{
 assert.equal(frontendVersion(),backendVersion())
})

test('only purposes that actually have a consumer are offered to users',()=>{
 const src=read('web/app/src/constants/contributionText.ts')
 assert.match(src,/OPEN_PURPOSES\s*=\s*\['model_training'\]\s*as const/)
})

test('consent copy makes no unfulfillable promises (no day counts, no doctor-review claim)',()=>{
 const src=read('web/app/src/constants/contributionText.ts')
 const body=src.slice(src.indexOf('export const TRAINING_TEXT'))
 assert.doesNotMatch(body,/\d+\s*(天|日|个工作日)/,'withdrawal copy must not promise a number of days')
 assert.doesNotMatch(body,/医生/,'copy must not claim doctor review before it exists')
 assert.match(body,/撤回/); assert.match(body,/不会公开展示/); assert.match(body,/无法完全/)
})

test('invite is never shown without an explicit opt-in; defaults are the narrowest scope',()=>{
 const card=read('web/app/src/components/contribution/ContributionInviteCard.vue')
 assert.match(card,/ref<GrantScope>\('future_only'\)/)
 assert.match(card,/localStorage\.setItem\(COOLDOWN_KEY/)
 assert.match(card,/s\.grants_enabled && !s\.active\.model_training/)
})

test('every micro question the backend serves has an explicit unknown-style option',()=>{
 const py=read('web/backend/services/self_report.py')
 const qs=[...py.matchAll(/"(Q\d)": \{[\s\S]*?"repeat_after_days"/g)].map(m=>m[0])
 assert.equal(qs.length,7)
 for(const q of qs) assert.match(q,/UNKNOWN|"unknown"/,q.slice(0,12))
})

test('new UI uses RemixIcon only and theme tokens, not emoji or hard-coded colours',()=>{
 for(const f of ['web/app/src/components/contribution/MicroAskCard.vue','web/app/src/components/contribution/ContributionInviteCard.vue','web/app/src/views/DataContributionPage.vue']){
  const s=read(f)
  assert.doesNotMatch(s,/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u,f+' contains emoji')
  assert.doesNotMatch(s,/#[0-9a-fA-F]{6}\b/,f+' hard-codes a hex colour')
  assert.doesNotMatch(s,/emerald-/,f+' uses emerald-*')
  assert.doesNotMatch(s,/<a\s+href="\//,f+' uses <a href> for internal navigation')
 }
})
