const {test}=require('node:test')
const assert=require('node:assert/strict')
const {readFileSync}=require('node:fs'),{createRequire}=require('node:module'),path=require('node:path')
const req=createRequire(path.resolve('web/app/package.json')),vue=req('vue'),ts=req('typescript')
function harness(initial=false){
 let now=1000,timer=null,unmount,cleared=0;const active=vue.ref(initial)
 const code=ts.transpileModule(readFileSync('web/app/src/composables/useAnalysisCountdown.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
 const out={};new Function('exports','require','Date','setInterval','clearInterval',code)(out,name=>{assert.equal(name,'vue');return {...vue,onBeforeUnmount:fn=>unmount=fn}},{now:()=>now},fn=>{timer=fn;return 1},()=>{timer=null;cleared++})
 const state=out.useAnalysisCountdown(()=>active.value)
 return {state,active,tick:ms=>{now+=ms;if(timer)timer()},running:()=>!!timer,unmount:()=>unmount(),cleared:()=>cleared}
}
test('starts at reference budget, updates from elapsed time, and tolerates a background tab',async()=>{
 const h=harness();assert.equal(h.running(),false);h.active.value=true;await vue.nextTick();assert.equal(h.state.remaining.value,90)
 h.tick(1000);assert.equal(h.state.remaining.value,89);h.tick(25000);assert.equal(h.state.remaining.value,64)
 h.tick(100000);assert.equal(h.state.remaining.value,0);assert.equal(h.state.overdue.value,true);assert.equal(h.running(),false)
 h.unmount()
})
test('cancel, restart and unmount release timer without continuing stale countdown',async()=>{
 const h=harness(true);h.tick(8000);h.active.value=false;await vue.nextTick();assert.equal(h.running(),false)
 h.tick(5000);assert.equal(h.state.remaining.value,82);h.active.value=true;await vue.nextTick();assert.equal(h.state.remaining.value,90)
 h.unmount();assert.equal(h.running(),false);assert.ok(h.cleared()>=2)
})
