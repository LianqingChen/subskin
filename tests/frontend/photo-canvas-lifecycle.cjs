const {test}=require('node:test');const assert=require('node:assert/strict');const {readFileSync}=require('node:fs');const {createRequire}=require('node:module');const path=require('node:path')
const req=createRequire(path.resolve('web/app/package.json')),vue=req('vue'),ts=req('typescript')
function evaluate(file,deps={}){const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;const out={};new Function('exports','require',code)(out,name=>{assert.ok(name in deps,name);return deps[name]});return out}
const pixels=evaluate('web/app/src/utils/photo-mask.ts')
global.requestAnimationFrame=()=>1;global.cancelAnimationFrame=()=>{}
function harness(loader){
 let mount,unmount;const readyState={masks:{width:32,height:32,skin:new Uint8Array(1024).fill(1),lesion:new Uint8Array(1024)}}
 const options=vue.reactive({image:'synthetic',skin:'skin',lesion:'lesion',tool:'lesion',brushSize:4,editable:true,busy:false})
 const target=vue.ref({setPointerCapture(){},hasPointerCapture(){return false},releasePointerCapture(){},getBoundingClientRect:()=>({left:0,top:0,width:32,height:32}),toDataURL:()=> 'fused'})
 const module=evaluate('web/app/src/composables/usePhotoMaskCanvas.ts',{'vue':{...vue,onMounted:fn=>mount=fn,onBeforeUnmount:fn=>unmount=fn},'@/utils/photo-mask':pixels,'@/utils/photo-mask-canvas':{loadPhotoMasks:loader|| (async()=>readyState),renderPhotoMasks(){},exportPhotoMasks:s=>({skinMaskDataUrl:[...s.masks.skin],lesionMaskDataUrl:[...s.masks.lesion]})}})
 const state=module.usePhotoMaskCanvas(options,target);return {state,options,readyState,mount:()=>mount(),unmount:()=>unmount()}
}
const event=(x,y,id=1)=>({clientX:x,clientY:y,pointerId:id,isPrimary:id===1,button:0,preventDefault(){this.defaultPrevented=true}})
test('paint, erase both layers, and export the visible result without zoom transforms',async()=>{
 const h=harness();await h.mount();h.state.down(event(5,5));assert.equal(h.state.snapshot(),null);h.state.up(event(12,5))
 assert.equal(h.state.snapshot().lesionMaskDataUrl[5*32+8],1)
 h.options.tool='eraser';await vue.nextTick();h.state.down(event(8,5));h.state.up(event(8,5));assert.equal(h.state.snapshot().lesionMaskDataUrl[5*32+8],0);assert.equal(h.state.snapshot().skinMaskDataUrl[5*32+8],0)
 h.options.tool='skin';await vue.nextTick();h.options.tool='eraser';await vue.nextTick();h.state.down(event(12,5));h.state.up(event(12,5));assert.equal(h.state.snapshot().skinMaskDataUrl[5*32+12],0)
})
test('second finger rolls back an accidental stroke instead of zooming or marking',async()=>{
 const h=harness();await h.mount();h.state.down(event(5,5));h.state.down(event(10,10,2));assert.equal(h.state.snapshot().lesionMaskDataUrl.some(Boolean),false)
})
test('late load after unmount cannot enable confirmation; load failure stays blocked',async()=>{
 let resolve;const h=harness(()=>new Promise(r=>resolve=r));const pending=h.mount();h.unmount();resolve(h.readyState);await pending;assert.equal(h.state.ready.value,false)
 const bad=harness(async()=>{throw new Error('加载失败')});await bad.mount();assert.equal(bad.state.ready.value,false);assert.equal(bad.state.snapshot(),null)
})
test('missing skin is recoverable by painting and busy state blocks changes',async()=>{
 const h=harness();h.readyState.masks.skin.fill(0);await h.mount();assert.equal(h.state.snapshot(),null);assert.match(h.state.error.value,/皮肤/)
 h.options.tool='skin';await vue.nextTick();h.state.down(event(5,5));h.state.up(event(5,5));assert.equal(h.state.error.value,'');assert.ok(h.state.snapshot())
 h.options.busy=true;h.state.down(event(20,20));h.state.up(event(20,20));assert.equal(h.readyState.masks.skin[20*32+20],0)
})

test('accepted strokes prevent page defaults; foreign cancellation cannot erase the active stroke',async()=>{
 const h=harness();await h.mount();const down=event(5,5);h.state.down(down);assert.equal(down.defaultPrevented,true)
 h.state.cancelStroke(event(8,8,2));assert.equal(h.state.painting.value,true)
 const move=event(12,5);h.state.move(move);assert.equal(move.defaultPrevented,true)
 const up=event(15,5);h.state.up(up);assert.equal(up.defaultPrevented,true)
 h.state.cancelStroke(event(15,5));assert.equal(h.state.snapshot().lesionMaskDataUrl[5*32+10],1)
})
test('cancelled pointer restores both masks and permits the next brush stroke',async()=>{
 const h=harness();await h.mount();h.state.down(event(5,5));h.state.move(event(12,5));h.state.cancelStroke(event(12,5))
 assert.equal(h.state.snapshot().lesionMaskDataUrl.some(Boolean),false)
 h.state.down(event(20,20));h.state.up(event(20,20));assert.equal(h.state.snapshot().lesionMaskDataUrl[20*32+20],1)
})

test('leaving the photo stops drawing and reentry does not connect across it',async()=>{
 const h=harness();await h.mount();h.state.down(event(3,3));h.state.move(event(5,3))
 const before=h.readyState.masks.lesion.slice();h.state.move(event(50,50));assert.deepEqual(h.readyState.masks.lesion,before)
 h.state.move(event(28,28));h.state.up(event(50,50));assert.equal(h.state.painting.value,false)
 assert.equal(h.readyState.masks.lesion[15*32+15],0);assert.equal(h.readyState.masks.lesion[28*32+28],1)
})
test('eraser consistently clears pink and blue regardless of the preceding tool',async()=>{
 for(const tool of ['skin','lesion']){const h=harness();await h.mount();h.options.tool=tool;h.state.down(event(10,10));h.state.up(event(10,10));h.options.tool='eraser';h.state.down(event(10,10));h.state.up(event(10,10));assert.equal(h.readyState.masks.skin[330],0);assert.equal(h.readyState.masks.lesion[330],0)}
})
