const {test}=require('node:test')
const assert=require('node:assert/strict')
const {readFileSync}=require('node:fs')
const {createRequire}=require('node:module')
const path=require('node:path')
const appRequire=createRequire(path.resolve('web/app/package.json'))
const ts=appRequire('typescript')
function load(file,deps){
 const js=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
 const result={};new Function('exports','require',js)(result,name=>name in deps?deps[name]:appRequire(name));return result
}
const dateFile='web/app/src/utils/capture-date.ts'
test('metadata date wins; camera always uses capture-day and never parses metadata',async()=>{
 let calls=0;const api=load(dateFile,{'./exif':{readPhotoTakenDate:async()=>{calls++;return '2025-06-07'}}})
 assert.equal((await api.defaultCaptureDate({},'gallery','2026-09-13')).date,'2025-06-07')
 assert.equal((await api.defaultCaptureDate({},'camera','2026-09-13')).date,'2026-09-13');assert.equal(calls,1)
})
test('missing, impossible and future dates fall back with explicit notice',async()=>{
 for(const date of [null,'2025-02-29','2026-02-31','2099-01-01','1899-01-01']){
  const api=load(dateFile,{'./exif':{readPhotoTakenDate:async()=>date}})
  const r=await api.defaultCaptureDate({},'gallery','2026-09-13');assert.equal(r.date,'2026-09-13');assert.match(r.note,/没有可用日期/)
 }
})
test('local calendar date and leap day preserved',()=>{
 const api=load(dateFile,{'./exif':{}})
 assert.equal(api.localToday(new Date(2026,8,13,0,1)),'2026-09-13')
 assert.equal(api.validPhotoDate('2024-02-29','2026-09-13'),true)
})
function upload(check){
 global.FileReader=class{readAsDataURL(){this.result='data:preview';this.onload()}}
 const api=load('web/app/src/composables/useVasiUpload.ts',{
  '@/api/vasi':{vasiApi:{checkPhotoQuality:check}},
  '@/composables/useToast':{useToast:()=>({show(){},error(){}})},
  axios:{isAxiosError:e=>!!e?.response||!!e?.code}
 });const u=api.useVasiUpload();u.setBodySite('face');return u
}
const good={overall:'good',suggestions:[]}
test('401 is a login error, photo retained, retry can succeed',async()=>{
 let bad=true;const u=upload(async()=>{if(bad)throw {response:{status:401}};return good})
 const file=new File(['photo'],'photo.jpg',{type:'image/jpeg'});u.selectFile(file)
 await new Promise(resolve=>setImmediate(resolve));assert.equal(u.uploadedImage.value,file);assert.equal(u.qualityNeedsLogin.value,true);assert.match(u.qualityError.value,/登录/)
 bad=false;await u.checkQuality(file);assert.equal(u.qualityResult.value.overall,'good');assert.equal(u.qualityError.value,'');assert.equal(u.qualityNeedsLogin.value,false)
})
test('a stale quality response cannot replace the next photo result',async()=>{
 const pending=[];const u=upload(()=>new Promise(resolve=>pending.push(resolve)))
 const a=new File(['a'],'a.jpg',{type:'image/jpeg'}),b=new File(['b'],'b.jpg',{type:'image/jpeg'})
 u.selectFile(a);u.selectFile(b);pending[1](good);await new Promise(resolve=>setImmediate(resolve));pending[0]({overall:'poor',suggestions:['bad']});await new Promise(resolve=>setImmediate(resolve))
 assert.equal(u.uploadedImage.value,b);assert.equal(u.qualityResult.value.overall,'good')
})
test('network failures retain file and permit retry, real poor quality remains poor',async()=>{
 let fail=true;const u=upload(async()=>{if(fail)throw {code:'ECONNABORTED'};return {overall:'poor',suggestions:['模糊']}})
 const f=new File(['f'],'f.jpg',{type:'image/jpeg'});u.selectFile(f);await new Promise(resolve=>setImmediate(resolve));assert.match(u.qualityError.value,/超时/);assert.equal(u.uploadedImage.value,f)
 fail=false;await u.checkQuality(f);assert.equal(u.qualityResult.value.overall,'poor')
})
test('capture UI has date wheel and retry, without angle or calendar gate',()=>{
 const source=readFileSync('web/app/src/components/tracker/AssessmentCapture.vue','utf8')
 assert.ok(!source.includes('type="date"'));assert.ok(!source.includes('context.view'));assert.ok(source.includes('DateWheelPicker'));assert.ok(source.includes('重新检查照片'))
 const page=readFileSync('web/app/src/views/AssessmentPage.vue','utf8');assert.ok(!page.includes('!context.value.view'));assert.ok(page.includes('generation !== dateGeneration'));assert.ok(page.includes("fileSelected(file, 'camera')"))
})
