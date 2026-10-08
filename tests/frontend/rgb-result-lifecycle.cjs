const {test}=require('node:test')
const assert=require('node:assert/strict')
const {readFileSync}=require('node:fs')
const {createRequire}=require('node:module')
const path=require('node:path')
const req=createRequire(path.resolve('web/app/package.json'));const ts=req('typescript');const vue=req('vue')
const snapshot={id:7,image_url:'/synthetic.png',body_site:'face',assessment_source:'rgb-tools-v1',measurement:{status:'unavailable',annotation:{protocol:'skin-seg-v2',review_state:'pending'}}}
function harness(assess){
 let unmount;const cancelled=[],abandoned=[]
 const code=ts.transpileModule(readFileSync('web/app/src/composables/useVasiAssess.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
 const exports={};const deps={vue:{...vue,onBeforeUnmount:fn=>unmount=fn},'@/stores/auth':{useAuthStore:()=>({user:{id:1},isLoggedIn:true})},'@/api/vasi':{vasiApi:{getAssessment:async()=>snapshot,abandonAssessment:async id=>abandoned.push(id)}},'@/api/rgb-segmentation':{rgbApi:{assess,cancel:async id=>cancelled.push(id)},RGBTaskError:class extends Error{}},'@/composables/useToast':{useToast:()=>({error(){},success(){}})},'@/utils/assessment-errors':{assessmentError:()=>''},'./useVasiAssessment':{}}
 new Function('exports','require',code)(exports,name=>{assert.ok(name in deps,name);return deps[name]})
 const state=exports.useVasiAssess();return {state,cancelled,abandoned,unmount:()=>unmount()}
}
test('leaving a completed review does not cancel or abandon its record',async()=>{
 const h=harness(async()=>({jobId:'done',assessmentId:7}))
 await h.state.submitAssessment({},'face');assert.equal(h.state.assessmentResult.value.id,7)
 h.unmount();await new Promise(r=>setImmediate(r));assert.deepEqual(h.cancelled,[]);assert.deepEqual(h.abandoned,[])
})
test('leaving while a job is pending aborts it and ignores late results',async()=>{
 let finish,signal;const h=harness(async(_image,_site,_ctx,s)=>{signal=s;return new Promise(resolve=>finish=resolve)})
 const pending=h.state.submitAssessment({},'face');h.unmount();assert.equal(signal.aborted,true)
 finish({jobId:'late',assessmentId:7});await pending
 assert.equal(h.state.assessmentResult.value,null);assert.deepEqual(h.cancelled,['late'])
})
test('explicit discard still abandons the draft',async()=>{
 const h=harness(async()=>({jobId:'done',assessmentId:7}));await h.state.submitAssessment({},'face');await h.state.cancelAssessment();assert.deepEqual(h.abandoned,[7])
})
