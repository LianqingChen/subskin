const {test}=require('node:test')
const assert=require('node:assert/strict')
const {readFileSync}=require('node:fs')
const {createRequire}=require('node:module')
const path=require('node:path')
const req=createRequire(path.resolve('web/app/package.json'));const ts=req('typescript')
global.crypto=global.crypto || require('node:crypto').webcrypto
function load(client){
 const code=ts.transpileModule(readFileSync('web/app/src/api/rgb-segmentation.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
 const result={};new Function('exports','require',code)(result,name=>{
  if(name==='./client')return {default:client}
  if(name==='axios')return {isAxiosError:e=>e?.axios===true}
  throw new Error('Unexpected dependency '+name)
 });return result
}
const done={id:'synthetic-job',operation:'assessment',state:'completed',stage:'completed',assessment_id:7,error_code:null,result:{protocol:'skin-seg-v2',mask_revision:'synthetic-revision',status:'review_required'}}
const photo=new File(['test'],'synthetic.png',{type:'image/png'})
const capability={data:{protocol:'skin-seg-v2',worker_ready:true}}
test('new analysis uses durable RGB jobs and never calls the LLM assess endpoint',async()=>{
 const urls=[];const {rgbApi}=load({get:async url=>{urls.push(url);return capability},post:async(url,body)=>{urls.push(url);assert.ok(body.get('idempotency_key'));return {data:done}}})
 const result=await rgbApi.assess(photo,'face',{capture_date:'2026-09-13'},new AbortController().signal,()=>{})
 assert.deepEqual(result,{jobId:'synthetic-job',assessmentId:7});assert.ok(urls.includes('/vasi/segmentation-jobs'));assert.ok(!urls.includes('/vasi/assess'))
})
test('uncertain upload retry reuses the exact idempotency key',async()=>{
 const keys=[];const {rgbApi}=load({get:async()=>capability,post:async(url,body)=>{keys.push(body.get('idempotency_key'));if(keys.length===1)throw {axios:true};return {data:done}}})
 await rgbApi.assess(photo,'face',{},new AbortController().signal,()=>{});assert.equal(keys.length,2);assert.equal(keys[0],keys[1])
})
test('cancel during admission cancels the acknowledged server job instead of rendering a late result',async()=>{
 const controller=new AbortController();let release;const calls=[]
 const {rgbApi,RGBTaskError}=load({get:async()=>capability,post:async(url)=>{calls.push(url);if(url==='/vasi/segmentation-jobs')return await new Promise(resolve=>release=resolve);return {data:{}}}})
 const pending=rgbApi.assess(photo,'face',{},controller.signal,()=>{});await new Promise(resolve=>setImmediate(resolve));controller.abort();release({data:{...done,state:'queued',stage:'queued',assessment_id:null}})
 await assert.rejects(pending,e=>e instanceof RGBTaskError && e.code==='CANCELLED');assert.ok(calls.includes('/vasi/segmentation-jobs/synthetic-job/cancel'))
})
test('failed quality task is not a zero-area success',async()=>{
 const {rgbApi,RGBTaskError}=load({get:async()=>capability,post:async()=>({data:{...done,state:'failed',assessment_id:null,error_code:'QUALITY_INFORMATION_LOST',result:null}})})
 await assert.rejects(rgbApi.assess(photo,'face',{},new AbortController().signal,()=>{}),e=>e instanceof RGBTaskError && e.code==='QUALITY_INFORMATION_LOST')
})
test('reference update includes revision and explicit acknowledgement',async()=>{
 let payload;const {rgbApi}=load({patch:async(url,body)=>{payload={url,body};return {data:{measurement:{status:'measured'}}}}})
 await rgbApi.review('job','revision','skin','lesion',true)
 assert.equal(payload.url,'/vasi/segmentation-jobs/job/review');assert.deepEqual(payload.body,{base_revision:'revision',skin_mask:'skin',lesion_mask:'lesion',acknowledged:true})
})
