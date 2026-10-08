const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module')
const req=createRequire(path.resolve('web/app/package.json')),ts=req('typescript'),vue=req('vue')
function harness(selector){
 let unmount,painted=0,changed=0;const warnings=[]
 const skin={width:10,height:10,value:'skin-v1',toDataURL(){return this.value}},lesion={width:10,height:10,value:'lesion-v1',toDataURL(){return this.value}}
 global.Image=class{constructor(){this.naturalWidth=10;this.naturalHeight=10}set src(v){queueMicrotask(()=>this.onload())}}
 const exports={};const code=ts.transpileModule(fs.readFileSync('web/app/src/composables/useRemoteMaskSelection.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
 new Function('exports','require',code)(exports,name=>{
  if(name==='vue')return {...vue,onBeforeUnmount:fn=>unmount=fn}
  if(name==='@/api/rgb-segmentation')return {RGBTaskError:class extends Error{}}
  if(name==='@/utils/assessment-errors')return {assessmentError:()=>''}
  if(name==='@/composables/useToast')return {useToast:()=>({warning:m=>warnings.push(m)})}
  if(name==='@/utils/lesionMaskTools')return {paintMask:()=>{painted++},readMask:()=>new Uint8Array(100)}
  throw new Error(name)
 })
 const controller=exports.useRemoteMaskSelection({selector:()=>selector,skin:()=>skin,lesion:()=>lesion,changed:()=>changed++})
 return {controller,skin,lesion,warnings,unmount:()=>unmount(),counts:()=>({painted,changed})}
}
test('late remote mask does not replace newer local edits',async()=>{
 let resolve;const h=harness(()=>new Promise(r=>resolve=r));const pending=h.controller.select(5,5)
 h.skin.value='skin-v2';resolve('data:synthetic');await pending
 assert.deepEqual(h.counts(),{painted:0,changed:0});assert.match(h.warnings[0],/标注已变化/)
})
test('unmount aborts the refinement signal and ignores its result',async()=>{
 let resolve,signal;const h=harness(input=>{signal=input.signal;return new Promise(r=>resolve=r)})
 const pending=h.controller.select(5,5);h.unmount();assert.equal(signal.aborted,true);resolve('data:synthetic');await pending
 assert.deepEqual(h.counts(),{painted:0,changed:0});assert.equal(h.warnings.length,0)
})
