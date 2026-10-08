// Browser regression against staging; all API traffic uses synthetic fixtures.
const {chromium} = require(process.env.SUBSKIN_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'); const assert = require('node:assert/strict');
const out = process.env.SUBSKIN_BRUSH_QA_OUT || '/tmp/subskin-share-theme-qa'; fs.mkdirSync(out,{recursive:true});
const fixturePath=process.env.SUBSKIN_ART_FIXTURE || '/tmp/subskin-art-chain.json';
const artFixture=fs.existsSync(fixturePath)?JSON.parse(fs.readFileSync(fixturePath,'utf8')):{plan:{theme:'sky',title:'合成轮廓的风景。'},image_data_url:null};let artStarts=0,artPolls=0;
const width=Number(process.env.QA_WIDTH || 375),height=Number(process.env.QA_HEIGHT || 812),mobile=width<768;
(async()=>{
 const browser = await chromium.launch({headless:true,executablePath:"/usr/bin/google-chrome"}); const context = await browser.newContext({viewport:{width,height},serviceWorkers:'block',isMobile:mobile,hasTouch:mobile});
 const page = await context.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 if(!artFixture.image_data_url)artFixture.image_data_url=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=512;c.height=512;const g=c.getContext('2d');g.fillStyle='#9ec8b0';g.fillRect(0,0,512,512);return c.toDataURL('image/jpeg')});
 const fixture=await page.evaluate(()=>{
  const c=document.createElement('canvas');c.width=512;c.height=512;const g=c.getContext('2d');
  const shape=new Path2D();shape.ellipse(185,220,115,120,0,0,Math.PI*2);shape.moveTo(200,207.5);shape.ellipse(157.5,207.5,42.5,52.5,0,0,Math.PI*2);shape.moveTo(390,382.5);shape.ellipse(365,382.5,25,22.5,0,0,Math.PI*2);
  g.fillStyle='rgb(0,170,100)';g.fill(shape,'evenodd');const lesion=c.toDataURL();
  g.fillStyle='rgb(96,165,250)';g.fillRect(0,0,512,512);const skin=c.toDataURL();
  g.fillStyle='#dfb995';g.fillRect(0,0,512,512);g.fillStyle='#f7e9dd';g.fill(shape,'evenodd');return {lesion,skin,photo:c.toDataURL()};
 });
 const user={id:987654321,username:'synthetic',uid:null,is_active:true,is_admin:false,avatar_url:null,created_at:'2030-01-01'};
 await context.addInitScript(user=>{localStorage.setItem('subskin_token','synthetic-browser-fixture');localStorage.setItem('subskin_user',JSON.stringify(user));localStorage.setItem('subskin_disclaimer_accepted','true')},user);
 const uploadedPngs=[];const titles={sky:'把云朵轻轻收进自己的天空。',island:'每座小岛都有自己的海岸。',stars:'让点点星光照亮平凡的今天。'};
 const calls=[]; let uploads=0; let fixtureMode='normal'; let completed=false,review=null,failStory=false,posts=0;const generated={...artFixture.plan,source:'ai',revision:'synthetic-revision'};
 await page.route('**/api/**', async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;calls.push({path,method:req.method(),body:req.postData()});
  let data={};const theme=req.method()==='GET'?new URL(req.url()).searchParams.get('theme'):req.postData()?.startsWith('{')?JSON.parse(req.postData()).theme:undefined;
  if(path.endsWith('/story/art')) {if(req.method()==='POST'){artStarts++;data={status:'pending',revision:'synthetic-revision',theme,model:'qwen-image-3.0-pro'}}else{artPolls++;data={status:'ready',revision:'synthetic-revision',theme,model:'qwen-image-3.0-pro',image_data_url:artFixture.image_data_url}}}
  else if(path.endsWith('/story')) { if(failStory){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'创意暂未生成'})});return} data={...generated,theme,title:titles[theme]}; }
  else if(path==='/api/community/categories') data=[{id:7,name:'生活记录'}];
  else if(path==='/api/users/me') data=user;
  else if(path==='/api/vasi/history') data={items:[],total:0};
  else if(path==='/api/vasi/check-photo-quality') data={overall:'good',suggestions:[]};
  else if(path==='/api/vasi/rgb-capabilities') data={protocol:'skin-seg-v2',worker_ready:true};
  else if(path.endsWith('/review')) {review=JSON.parse(req.postData()); data={final_area_percentage:10,measurement:{status:'measured',annotation:{protocol:'skin-seg-v2',review_state:'user_reviewed'}}};}
  else if(path.startsWith('/api/vasi/segmentation-jobs')) data={id:'synthetic-job',state:completed?'completed':'queued',stage:completed?'completed':'queued',assessment_id:completed?987654321:null};
  else if(path.includes('/vasi/assess/')) data={id:987654321,record_status:'active',body_site:'left_hand',image_url:fixture.photo,skin_layer_data_url:fixture.skin,lesion_layer_data_url:fixtureMode==='missing' ? null : fixture.lesion,vasi_score:0,area_percentage:12.4,measurement:{version:'photo-v1',status:'measured',scope:'photo',area_percentage:12.4,clinical_vasi_valid:false,region_count:2,lesion_pixels:1240,skin_pixels:10000,reasons:[],annotation:{protocol:'skin-seg-v2',review_state:fixtureMode==='pending'?'pending':'user_reviewed',mask_revision:'synthetic-revision',job_id:'synthetic-job'}},observation:{capture_date:'2030-06-10',label:'左手'}};
  else if(path==='/api/patient-profiles/') data=[{id:1,name:'',is_self:true,relationship:'本人',gender:'女',birth_date:'2000-01-01'},{id:2,name:'',is_self:false,relationship:'孩子',gender:'男',birth_date:'2020-01-01'}];
  else if(path.includes('file-token')) data={token:'synthetic-file',expires_in:300};
  else if(path.includes('/notifications')) data={items:[],unread_count:0};
  else if(path.includes('/categories')||path.includes('/diaries')||path.includes('/tags')) data=[];
  else if(path.includes('/upload')) { const body=req.postDataBuffer(),start=body.indexOf(Buffer.from([137,80,78,71,13,10,26,10]));assert.ok(start>=0);let end=start+8;while(end<body.length){const size=body.readUInt32BE(end),type=body.toString('ascii',end+4,end+8);end+=size+12;if(type==='IEND')break}uploadedPngs.push(body.subarray(start,end).toString('base64'));uploads++;data={image_url:'/uploads/synthetic-'+uploads+'.png'}; }
  else if(path==='/api/community/posts' && req.method()==='POST') {posts++;data={id:987654322};}
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });


 await page.goto('https://staging.subskin.cn/assessment/vasi/987654321',{waitUntil:'networkidle'});
 const article=page.locator('article').filter({has:page.getByRole('heading',{name:'本次记录',exact:true})});
 const card=page.getByRole('img',{name:/轮廓创意卡：/});await card.waitFor({timeout:30000});await page.getByText('AI 图案 · AI 文案',{exact:true}).waitFor({timeout:30000});assert.ok(artStarts>0&&artPolls>0);
 assert.equal(await page.getByText('调整文案、档案和分享内容',{exact:true}).count(),0);
 assert.equal(await page.getByLabel('为谁制作',{exact:true}).count(),0);
 assert.equal(await page.getByRole('group',{name:'选择创意风格'}).count(),1);
 const styles=page.getByRole('group',{name:'选择创意风格'});
 for(const [id,label] of [['island','海岛'],['stars','星光']]){await styles.getByRole('button',{name:label,exact:true}).click();await page.getByRole('img',{name:'轮廓创意卡：'+titles[id],exact:true}).waitFor();await page.getByText('AI 图案 · AI 文案',{exact:true}).waitFor();assert.equal(await styles.getByRole('button',{name:label,exact:true}).getAttribute('aria-pressed'),'true')}
 assert.match(await article.innerText(),/12.4%/);
 assert.ok((await article.innerText()).length<330,'report text should remain concise');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 const headingBoxes=await article.locator('h2').evaluateAll(els=>els.map(el=>({height:el.clientHeight,line:parseFloat(getComputedStyle(el).lineHeight)})));
 assert.ok(headingBoxes.every(b=>b.height<=b.line+1),'section titles use one line');
 await article.screenshot({path:out+'/report-'+width+'.png'});
 const posterUrl=await card.getAttribute('src');
 const image=await card.evaluate(async img=>{const b=await fetch(img.src).then(r=>r.blob());return Array.from(new Uint8Array(await b.arrayBuffer()))});fs.writeFileSync(out+'/creative-'+width+'.png',Buffer.from(image));
 const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'保存图片',exact:true}).click();const download=await downloadPromise;assert.match(download.suggestedFilename(),/轮廓故事/);
 await page.evaluate(()=>{navigator.canShare=()=>true;navigator.share=async data=>{window.__shared={title:data.title,url:data.url,files:data.files.map(f=>({type:f.type,size:f.size}))}}});
 await page.getByRole('button',{name:'更多分享',exact:true}).click();assert.equal((await page.evaluate(()=>window.__shared)).files[0].type,'image/png');
 await page.getByRole('button',{name:'分享到分享',exact:true}).click();const dialog=page.getByRole('dialog',{name:'公开发布确认'});await dialog.waitFor();
 assert.equal(await dialog.locator('img').count(),3);assert.equal(uploads,0);assert.equal(posts,0);
 await dialog.screenshot({path:out+'/preview-'+width+'.png'});
 await dialog.getByRole('button',{name:'取消',exact:true}).click();assert.equal(posts,0);
 await page.evaluate(()=>document.documentElement.classList.add('dark'));await article.screenshot({path:out+'/report-dark-'+width+'.png'});
 await page.getByRole('button',{name:'分享到分享',exact:true}).click();await dialog.waitFor();
 await dialog.getByRole('button',{name:'确认公开',exact:true}).click();
 await page.waitForURL('**/community/987654322');
 assert.equal(posts,1);assert.equal(uploads,3);
 const posted=JSON.parse(calls.find(c=>c.path==='/api/community/posts'&&c.method==='POST').body);
 assert.equal(posted.images.length,3);assert.equal(posted.public_ack,true);assert.equal(posted.is_private,false);assert.equal(posted.title,titles.stars);assert.match(posted.content,/12.4%/);assert.ok(posted.content.length<330);assert.match(posted.content,/2 处/);assert.match(posted.content,/1240/);assert.match(posted.content,/10000/);assert.deepEqual(posted.image_metas.map(m=>m.image_url),posted.images);assert.equal(posted.image_metas[2].body_site,'left_hand');
 const pixelOrder=await page.evaluate(async buffers=>{const values=[];for(const b of buffers){const img=new Image();img.src='data:image/png;base64,'+b;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const ctx=c.getContext('2d');ctx.drawImage(img,0,0);values.push({width:c.width,height:c.height,rgb:Array.from(ctx.getImageData(10,10,1,1).data)})}return values},uploadedPngs);
 assert.equal(pixelOrder[0].width,1080);assert.equal(pixelOrder[0].height,1440);assert.deepEqual(pixelOrder[2].rgb,[223,185,149,255]);assert.notDeepEqual(pixelOrder[1].rgb,pixelOrder[2].rgb);assert.deepEqual(posted.images,['/uploads/synthetic-1.png','/uploads/synthetic-2.png','/uploads/synthetic-3.png']);
 // Same reviewed revision returns to the existing published post instead of creating duplicates.
 await page.goto('https://staging.subskin.cn/assessment/vasi/987654321',{waitUntil:'networkidle'});await card.waitFor();await page.getByRole('group',{name:'选择创意风格'}).getByRole('button',{name:'星光',exact:true}).click();await page.getByText('AI 图案 · AI 文案',{exact:true}).waitFor();
 await page.getByRole('button',{name:'分享到分享',exact:true}).click();await page.waitForURL('**/community/987654322');assert.equal(posts,1);
 failStory=true;await page.goto('https://staging.subskin.cn/assessment/vasi/987654321',{waitUntil:'networkidle'});
 await page.getByText('AI文案暂未生成，已保留轮廓创意',{exact:false}).waitFor();assert.match(await article.innerText(),/12.4%/);assert.equal(await page.getByRole('button',{name:'保存图片',exact:true}).isDisabled(),false);
 console.log(JSON.stringify({width,height,passed:true,posts,uploads,checks:['three explicit styles','uploaded PNG order: creative, overlay, original','complete image metadata','creative caption and real measurement values','no settings','one-line headings','short accurate summary','single three-image publish','cancel publishes nothing','download and system share','repeat publish guard','AI failure retains measurement'],errors}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
