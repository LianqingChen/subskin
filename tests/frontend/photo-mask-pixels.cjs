const {test}=require('node:test')
const assert=require('node:assert/strict')
const {readFileSync}=require('node:fs');const {createRequire}=require('node:module');const path=require('node:path')
const req=createRequire(path.resolve('web/app/package.json'));const ts=req('typescript')
const exportsObject={};const code=ts.transpileModule(readFileSync('web/app/src/utils/photo-mask.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
new Function('exports',code)(exportsObject)
const {combineCandidates,paintPhotoMasks,overlayPixels,binaryPixels,alphaMask}=exportsObject
function masks(){return {width:32,height:32,skin:new Uint8Array(1024),lesion:new Uint8Array(1024)}}
test('candidates prefill only within skin; original arrays remain unchanged',()=>{
 const skin=new Uint8Array([1,1,0]),lesion=new Uint8Array([1,0,0]),candidate=new Uint8Array([0,1,1])
 assert.deepEqual([...combineCandidates(skin,lesion,candidate)],[1,1,0]);assert.deepEqual([...lesion],[1,0,0])
})
test('blue and pink composite uses 60% transparency once, binary export remains opaque',()=>{
 const m={width:3,height:1,skin:new Uint8Array([1,1,0]),lesion:new Uint8Array([0,1,0])}
 assert.deepEqual([...overlayPixels(m)],[147,197,253,102,249,168,212,102,0,0,0,0])
 assert.deepEqual([...alphaMask(binaryPixels(m.lesion))],[0,1,0]);assert.equal(binaryPixels(m.lesion)[7],255)
})
test('brushes replace each other and total skin counts each pixel once',()=>{
 const m=masks();paintPhotoMasks(m,'skin',false,[5,16],[26,16],4)
 paintPhotoMasks(m,'lesion',false,[12,16],[16,16],2)
 assert.equal(m.skin[16*32+14],1);assert.equal(m.lesion[16*32+14],1)
 paintPhotoMasks(m,'skin',false,[14,16],[14,16],1)
 assert.equal(m.skin[16*32+14],1);assert.equal(m.lesion[16*32+14],0)
 const white=m.lesion.reduce((s,v)=>s+v,0),total=m.skin.reduce((s,v)=>s+v,0)
 const normal=m.skin.reduce((s,v,i)=>s+(v&&!m.lesion[i]?1:0),0)
 assert.equal(normal+white,total)
 assert.equal(white/(normal+white),white/total)
})
test('lesion brush may add omitted skin and still keeps lesion inside total skin',()=>{
 const m=masks();paintPhotoMasks(m,'lesion',false,[5,5],[15,5],2)
 assert.ok(m.lesion.some(Boolean));assert.deepEqual(m.skin,m.lesion)
 assert.ok(m.lesion.every((v,i)=>!v||m.skin[i]))
})
test('lesion eraser keeps skin; skin eraser removes both masks',()=>{
 const m=masks();m.skin.fill(1);m.lesion.fill(1)
 paintPhotoMasks(m,'lesion',true,[10,10],[10,10],3);assert.equal(m.lesion[330],0);assert.equal(m.skin[330],1)
 paintPhotoMasks(m,'skin',true,[20,20],[20,20],3);assert.equal(m.lesion[660],0);assert.equal(m.skin[660],0)
})
