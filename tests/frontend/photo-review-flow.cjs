const {test}=require('node:test');const assert=require('node:assert/strict');const {readFileSync}=require('node:fs');const {createRequire}=require('node:module');const path=require('node:path')
const req=createRequire(path.resolve('web/app/package.json')),vue=req('vue'),ts=req('typescript'),{parse,compileScript}=req('@vue/compiler-sfc')
function harness(){
 const assess={lastAssessment:vue.ref(null),isUploading:vue.ref(false),isSubmittingContour:vue.ref(false),autoFinalized:vue.ref(false),annotatedImage:vue.ref(null),submitAssessment:async()=>{assess.lastAssessment.value={id:7,measurement:{annotation:{review_state:'pending'}}}},handleTwoLayerConfirm:async()=>{assess.autoFinalized.value=true}}
 const upload={uploadedImage:vue.ref({}),selectedBodySite:vue.ref('face'),qualityChecking:vue.ref(false),qualityResult:vue.ref({overall:'good'}),qualityNeedsLogin:vue.ref(false)}
 const deps={vue:{...vue,onMounted(){}},'vue-router':{useRoute:()=>({query:{}}),useRouter:()=>({replace(){},push(){}})},'@/stores/auth':{useAuthStore:()=>({isLoggedIn:true,user:{id:1}})},'@/composables/useToast':{useToast:()=>({warning(){},error(){}})},'@/composables/useVasiUpload':{useVasiUpload:()=>upload},'@/composables/useVasiAssess':{useVasiAssess:()=>assess},'@/composables/useVasiHistory':{useVasiHistory:()=>({})},'@/composables/useVasiShare':{useVasiShare:()=>({})},'@/composables/useComparisonHistory':{useComparisonHistory:()=>({})},'../../../shared/site-modules.json':{default:{modules:[]}},'@/constants/bodySites':{BODY_SITES:{}},'@/utils/capture-date':{},'@/utils/file-url':{},'@/composables/useQuickPhotoCompare':{}}
 const descriptor=parse(readFileSync('web/app/src/views/AssessmentPage.vue','utf8')).descriptor
 const code=ts.transpileModule(compileScript(descriptor,{id:'page'}).content,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
 const result={};new Function('exports','require',code)(result,name=>{if(name.endsWith('.vue'))return {default:{}};assert.ok(name in deps,name);return deps[name]})
 const state=result.default.setup({}, {expose(){}});state.context.value={capture_date:'2026-09-13'};return {state,assess}
}
test('successful upload immediately opens editable review, then confirms to result',async()=>{
 const h=harness();await h.state.submit();assert.equal(h.state.screen.value,'result');assert.equal(h.state.editing.value,true)
 await h.state.confirmMasks({skinMaskDataUrl:'skin',lesionMaskDataUrl:'pink',uncertaintyReviewed:true,annotatedImageDataUrl:'fused'})
 assert.equal(h.state.editing.value,false);assert.equal(h.assess.annotatedImage.value,'fused');assert.equal(h.assess.autoFinalized.value,true)
})
test('failed save retains editor and does not prepare a share image',async()=>{
 const h=harness();await h.state.submit();h.assess.handleTwoLayerConfirm=async()=>{throw new Error('network')}
 await h.state.confirmMasks({skinMaskDataUrl:'skin',lesionMaskDataUrl:'pink',uncertaintyReviewed:true,annotatedImageDataUrl:'fused'})
 assert.equal(h.state.editing.value,true);assert.equal(h.assess.annotatedImage.value,null)
})
