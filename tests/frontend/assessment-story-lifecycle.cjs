const {test}=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'),{createRequire}=require('node:module')
const req=createRequire(path.resolve('web/app/package.json')),vue=req('vue'),ts=req('typescript')
function evaluate(file,deps){const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;const out={};new Function('exports','require',code)(out,name=>{assert.ok(name in deps,name);return deps[name]});return out}
function harness(generate,generateArt=async()=>{throw new Error('synthetic unavailable')}){
 let unmount;const auth=vue.reactive({user:{id:1}}),props=vue.reactive({saved:true,lesion:'synthetic',result:{id:1,measurement:{annotation:{review_state:'user_reviewed',mask_revision:'a'}}}})
 const module=evaluate('web/app/src/composables/useAssessmentStory.ts',{
 vue:{...vue,onBeforeUnmount:fn=>unmount=fn},axios:{isAxiosError:e=>!!e.response},'@/stores/auth':{useAuthStore:()=>auth},'@/utils/file-url':{toProtectedFileUrl:v=>v},
 '@/api/assessment-story':{generateAssessmentStory:generate,generateAssessmentArtwork:generateArt},'@/utils/assessment-story/summary':{journalSummary:r=>({reviewed:r.measurement.annotation.review_state==='user_reviewed',revision:r.measurement.annotation.mask_revision})},
 '@/utils/assessment-story/content':{makeStory:()=>({title:'属于自己的轮廓风景'})},
 '@/utils/assessment-story/render':{loadStoryShape:async()=>({}),loadStoryImage:async()=>({}),renderStoryPoster:async input=>new Blob([input.artwork?'generated-pixels':'synthetic'])}})
 const scope=vue.effectScope();const state=scope.run(()=>module.useAssessmentStory(props));return {state,props,auth,unmount(){unmount();scope.stop()}}
}
const tick=()=>new Promise(r=>setTimeout(r,300)), story=revision=>({theme:'sky',title:'把一片晴空，轻轻握在手心。',source:'ai',revision})
test('automatic creation needs no settings and uses the current reviewed revision',async()=>{
 const calls=[];const h=harness(async(id,rev)=>{calls.push([id,rev]);return story(rev)});await tick();assert.deepEqual(calls,[[1,'a']]);assert.ok(h.state.blob.value);assert.equal(h.state.title.value,story('a').title);h.unmount()
})
test('pending review and missing masks never trigger AI requests',async()=>{
 let calls=0;const h=harness(async()=>{calls++;return story('a')});h.props.saved=false;await vue.nextTick();await tick();assert.equal(calls,0);assert.equal(h.state.blob.value,null);h.unmount()
})
test('late generation cannot replace a changed revision or resurrect an unmounted preview',async()=>{
 const pending=[];const h=harness((id,rev,signal)=>new Promise(resolve=>pending.push({resolve,rev,signal})));await tick();h.props.result.measurement.annotation.mask_revision='b';await tick();assert.equal(pending[0].signal.aborted,true)
 pending[1].resolve(story('b'));await tick();const url=h.state.url.value;pending[0].resolve(story('a'));await tick();assert.equal(h.state.url.value,url);assert.equal(h.state.story.value.revision,'b');h.unmount();assert.equal(h.state.url.value,'')
})
test('AI failures leave the saved record and support a manual retry',async()=>{
 let fail=true;const h=harness(async()=>{if(fail)throw new Error('timeout');return story('a')});await tick();assert.ok(h.state.notice.value);assert.equal(h.props.saved,true);assert.ok(h.state.blob.value);assert.equal(h.state.story.value.source,'template');fail=false;await h.state.load();assert.ok(h.state.blob.value);h.unmount()
})

test('403 keeps a real contour poster without pretending template words came from AI',async()=>{
 const h=harness(async()=>{throw {response:{status:403}}});await tick();assert.equal(h.state.needsConsent.value,true);assert.ok(h.state.blob.value);assert.equal(h.state.story.value.source,'template');assert.equal(h.state.error.value,'');h.unmount()
})
test('slow AI cannot delay the local contour art or replace it after unmount',async()=>{
 let finish;const h=harness(()=>new Promise(resolve=>finish=resolve));await tick();assert.ok(h.state.blob.value);assert.equal(h.state.loading.value,false);assert.equal(h.state.enhancing.value,true);h.unmount();finish(story('a'));await tick();assert.equal(h.state.url.value,'')
})

test('artwork finishes after the caption and upgrades the downloadable poster',async()=>{
 let finish;const h=harness(async()=>story('a'),()=>new Promise(r=>finish=r));await tick();assert.ok(h.state.blob.value);assert.equal(h.state.story.value.source,'ai');assert.equal(h.state.drawing.value,true)
 finish('data:image/jpeg;base64,synthetic');await tick();assert.equal(h.state.artGenerated.value,true);assert.equal(await h.state.blob.value.text(),'generated-pixels');h.unmount()
})
test('late artwork is ignored after the editor changes the record revision',async()=>{
 const pending=[];const h=harness(async(id,rev)=>story(rev),(id,rev)=>new Promise(r=>pending.push({rev,r})));await tick();h.props.result.measurement.annotation.mask_revision='b';await tick();
 pending[1].r('data:image/jpeg;base64,new');await tick();const current=h.state.url.value;pending[0].r('data:image/jpeg;base64,old');await tick();assert.equal(h.state.url.value,current);assert.equal(h.state.story.value.revision,'b');h.unmount()
})
test('image model failure retains the AI caption and basic contour poster',async()=>{
 const h=harness(async()=>story('a'));await tick();assert.equal(h.state.story.value.source,'ai');assert.ok(h.state.blob.value);assert.equal(h.state.artGenerated.value,false);assert.ok(h.state.artNotice.value);h.unmount()
})

test('style changes generate matching captions and ignore late artwork from another style',async()=>{
 const pending=[];const h=harness(async(id,rev,signal,theme)=>({...story(rev),theme}),(id,rev,signal,retry,theme)=>new Promise(r=>pending.push({theme,r,signal})));await tick()
 h.state.selectedTheme.value='island';await tick();assert.equal(pending[0].signal.aborted,true);assert.equal(h.state.story.value.theme,'island')
 pending[1].r('data:image/jpeg;base64,island');await tick();const latest=h.state.url.value;pending[0].r('data:image/jpeg;base64,sky');await tick();assert.equal(h.state.url.value,latest);assert.equal(h.state.story.value.theme,'island');h.unmount()
})
