// Executes the shipped Vue script against deterministic media/DOM stubs.
// This is a unit regression suite, not browser or physical-camera acceptance.
const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const path = require('node:path')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const appRequire = createRequire(path.resolve('web/app/package.json'))
const { parse } = appRequire('@vue/compiler-sfc')
const ts = appRequire('typescript')
const { ref } = appRequire('vue')
function deferred() { let resolve, reject; const promise = new Promise((yes,no) => { resolve=yes; reject=no }); return {promise,resolve,reject} }
function media() { const track={stopped:0,stop(){this.stopped++}};return {track,getTracks:()=>[track]} }
function harness() {
  const source=readFileSync('web/app/src/components/tracker/BodyPartCamera.vue','utf8')
  const content=parse(source).descriptor.scriptSetup.content.replace(/^import .*\n/gm,'')
  const js=ts.transpileModule(content,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.None}}).outputText
  const requests=[],emitted=[],watchers=[],dispose=[],blobs=[],canvases=[],listeners=new Map()
  const props={modelValue:true,bodyPart:'left_hand',baselineUrl:null}
  const video={videoWidth:1920,videoHeight:1080,srcObject:null,readyState:4,play:async()=>{},pause(){}}
  const element={focus(){},querySelectorAll:()=>[]}
  const doc={hidden:false,activeElement:element,body:{style:{overflow:''}},
    addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:name=>listeners.delete(name),
    createElement:()=>{ const canvas={width:0,height:0,drawn:null,getContext:()=>({drawImage(...args){canvas.drawn=args}}),toBlob:fn=>blobs.push(fn)};canvases.push(canvas);return canvas }}
  const win={addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:name=>listeners.delete(name)}
  const nav={mediaDevices:{getUserMedia(){const d=deferred();requests.push(d);return d.promise}}}
  const code=new Function('ref','watch','nextTick','onUnmounted','defineProps','defineEmits','PART_LABELS','toProtectedFileUrl','navigator','document','window','File',js+'\nreturn {start,stop,capture,video,error,loading,facing, ...(typeof close === "function" ? {close} : {})};')
  const api=code(ref,(getter,fn)=>watchers.push(fn),()=>Promise.resolve(),fn=>dispose.push(fn),()=>props,()=>((...args)=>emitted.push(args)),{},v=>v,nav,doc,win,File)
  api.video.value=video
  return {api,requests,emitted,props,video,blobs,canvases,listeners,doc,watchers,dispose}
}
test('late permission rejection cannot poison a newer camera session',async()=>{
  const h=harness(),old=h.api.start(),latest=h.api.start(),m=media()
  h.requests[1].resolve(m);await latest
  h.requests[0].reject(new Error('denied'));await old
  assert.equal(h.api.error.value,'')
  h.api.stop()
})
test('playback failure releases camera tracks',async()=>{
  const h=harness(),m=media();h.video.play=async()=>{throw new Error('play failed')}
  const running=h.api.start();h.requests[0].resolve(m);await running
  assert.ok(m.track.stopped>0)
})
test('capture callback after close does not emit an old photograph',async()=>{
  const h=harness(),m=media(),running=h.api.start();h.requests[0].resolve(m);await running
  h.api.capture();h.props.modelValue=false;h.api.stop();h.blobs[0](new Blob(['synthetic'],{type:'image/jpeg'}))
  assert.equal(h.emitted.filter(e=>e[0]==='captured').length,0)
})
test('repeated shutter press creates one capture',async()=>{
  const h=harness(),m=media(),running=h.api.start();h.requests[0].resolve(m);await running
  h.api.capture();h.api.capture()
  assert.equal(h.blobs.length,1)
  h.api.stop()
})
test('late media stream is stopped when dialog was closed',async()=>{
  const h=harness(),m=media(),running=h.api.start();h.props.modelValue=false;h.api.stop();h.requests[0].resolve(m);await running
  assert.ok(m.track.stopped>0)
  assert.equal(h.video.srcObject,null)
})
async function openCamera(h) {
  const opened=h.watchers[0](true)
  await Promise.resolve()
  const m=media();h.requests[0].resolve(m);await opened
  return m
}
test('backgrounding closes dialog and releases the live camera',async()=>{
  const h=harness(),m=await openCamera(h)
  h.doc.hidden=true;h.listeners.get('visibilitychange')()
  assert.ok(m.track.stopped>0)
  assert.ok(h.emitted.some(e=>e[0]==='update:modelValue' && e[1]===false))
  h.props.modelValue=false;await h.watchers[0](false)
  assert.equal(h.doc.body.style.overflow,'')
  assert.equal(h.listeners.size,0)
})
test('pagehide releases camera and invalidates in-flight capture',async()=>{
  const h=harness(),m=await openCamera(h)
  h.api.capture();h.listeners.get('pagehide')();h.blobs[0](new Blob(['synthetic']))
  assert.ok(m.track.stopped>0)
  assert.equal(h.emitted.filter(e=>e[0]==='captured').length,0)
})
test('null photo encoding result is visible and can be retried',async()=>{
  const h=harness(),m=await openCamera(h)
  h.api.capture();h.blobs[0](null)
  assert.ok(h.api.error.value.includes('照片生成失败'))
  assert.ok(m.track.stopped>0)
  const retry=h.api.start();h.requests[1].resolve(media());await retry
  assert.equal(h.api.error.value,'')
  h.api.stop()
})
test('successful capture emits one full-sized image and closes camera',async()=>{
  const h=harness(),m=await openCamera(h)
  h.api.capture();const image=new Blob(['synthetic'],{type:'image/jpeg'});h.blobs[0](image)
  const capture=h.emitted.find(e=>e[0]==='captured')
  assert.equal(h.canvases[0].width,1920)
  assert.equal(h.canvases[0].height,1080)
  assert.deepEqual(h.canvases[0].drawn,[h.video,0,0])
  assert.equal(capture[1].type,'image/jpeg')
  assert.equal(capture[1].size,image.size)
  assert.ok(m.track.stopped>0)
  assert.equal(h.video.srcObject,null)
})
test('Escape closes the dialog without submitting a photograph',async()=>{
  const h=harness(),m=await openCamera(h)
  let prevented=false
  h.listeners.get('keydown')({key:'Escape',preventDefault(){prevented=true}})
  assert.ok(prevented)
  assert.ok(m.track.stopped>0)
  assert.equal(h.emitted.filter(e=>e[0]==='captured').length,0)
})
