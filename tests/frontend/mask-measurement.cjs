const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const {createRequire}=require('node:module');
const appRequire=createRequire(path.resolve('web/app/package.json'));const ts=appRequire('typescript');
const js=ts.transpileModule(fs.readFileSync('web/app/src/utils/maskMeasurement.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const mod={};new Function('exports',js)(mod);const {measureMaskPixels}=mod;
function rgba(n,indices){const data=new Uint8ClampedArray(n*4);for(const i of indices)data[i*4+3]=180;return data}
test('skin is denominator, not union with leaked lesion',()=>{const r=measureMaskPixels(rgba(100,[...Array(50).keys()]),rgba(100,[...Array(80).keys()]));assert.equal(r.areaPercentage,null);assert.equal(r.outsidePixels,30);assert.match(r.reason,/超出/)})
test('valid mask arithmetic uses alpha independently of displayed color',()=>{const r=measureMaskPixels(rgba(100,[...Array(80).keys()]),rgba(100,[0,1,2,3]));assert.equal(r.areaPercentage,5)})
test('missing skin never becomes 0 percent success',()=>{assert.equal(measureMaskPixels(rgba(100,[]),rgba(100,[])).areaPercentage,null)})
test('mismatched buffers rejected',()=>{assert.equal(measureMaskPixels(rgba(100,[1]),rgba(90,[1])).areaPercentage,null)})
test('small permitted raster-edge leakage excluded from numerator',()=>{const r=measureMaskPixels(rgba(100,[...Array(50).keys()]),rgba(100,[0,1,2,3,99]));assert.equal(r.areaPercentage,8)})

test('magic wand cannot grow into identical-colored non-skin pixels',()=>{
 const source=ts.transpileModule(fs.readFileSync('web/app/src/utils/lesionMaskTools.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;const tools={};new Function('exports',source)(tools);
 const data=new Uint8ClampedArray(10*10*4).fill(150),allowed=new Uint8Array(100);allowed.fill(1,0,50);const image={width:10,height:10,data};const edge={width:10,height:10,data:new Float32Array(100)};
 const result=tools.magicWandSelect(image,edge,2,2,{allowedMask:allowed});assert.equal(result.reduce((a,b)=>a+b,0),50);
 assert.equal(tools.magicWandSelect(image,edge,2,8,{allowedMask:allowed}).some(Boolean),false);
})
