// Verifies clipping alpha independently of the generated artistic pixels.
const {chromium}=require(process.env.SUBSKIN_PLAYWRIGHT_MODULE || 'playwright');const fs=require('fs'),assert=require('assert/strict');
const path=require('node:path'),req=require('node:module').createRequire(path.resolve('web/app/package.json')),ts=req('typescript');
const modules={};for(const name of ['mask','render'])modules[name]=ts.transpileModule(fs.readFileSync('web/app/src/utils/assessment-story/'+name+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome'});const page=await browser.newPage();
const result=await page.evaluate(async({modules,photo})=>{
 function load(code,deps){const output={};new Function('exports','require',code)(output,name=>deps[name]);return output}
 const maskModule=load(modules.mask,{}),render=load(modules.render,{'qrcode':{},'./content':{},'./mask':maskModule});
 const width=64,height=64,rgba=new Uint8ClampedArray(width*height*4);
 for(let y=8;y<38;y++)for(let x=8;x<38;x++){if(x>18&&x<28&&y>18&&y<28)continue;const p=(y*width+x)*4;rgba[p]=255;rgba[p+3]=255}
 rgba[(55*width+55)*4+3]=255;const shape=maskModule.analyzeStoryMask(rgba,width,height);
 const sample=document.createElement('canvas');sample.width=512;sample.height=512;const paint=sample.getContext('2d');const gradient=paint.createLinearGradient(0,0,512,512);gradient.addColorStop(0,'#bbddaa');gradient.addColorStop(1,'#226688');paint.fillStyle=gradient;paint.fillRect(0,0,512,512);
 const img=new Image();img.src=photo||sample.toDataURL();await img.decode();const checks=[];
 for(const theme of ['sky','island','stars']){const c=render.silhouette(shape,theme,img),pixels=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
 let mismatch=0,filled=0;for(let y=0;y<c.height;y++)for(let x=0;x<c.width;x++){const actual=pixels[(y*c.width+x)*4+3],expected=shape.pixels[(y+shape.bounds.y)*width+x+shape.bounds.x]?255:0;if(actual!==expected)mismatch++;if(actual)filled++}
 checks.push({theme,mismatch,filled,expected:shape.area})}return checks;
},{modules,photo:process.env.SUBSKIN_ART_FIXTURE?JSON.parse(fs.readFileSync(process.env.SUBSKIN_ART_FIXTURE)).image_data_url:null});
for(const check of result){assert.equal(check.mismatch,0);assert.equal(check.filled,check.expected)}console.log(JSON.stringify(result));await browser.close()})().catch(e=>{console.error(e);process.exit(1)});
