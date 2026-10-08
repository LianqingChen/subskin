// Browser regression against staging; all API traffic uses synthetic fixtures.
const {chromium} = require(process.env.SUBSKIN_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'); const assert = require('node:assert/strict');
const out = process.env.SUBSKIN_BRUSH_QA_OUT || '/tmp/subskin-editor-regression'; fs.mkdirSync(out,{recursive:true});
const width=Number(process.env.QA_WIDTH || 375),height=Number(process.env.QA_HEIGHT || 812),mobile=width<768;
(async()=>{
 const browser = await chromium.launch({headless:true,executablePath:"/usr/bin/google-chrome"}); const context = await browser.newContext({viewport:{width,height},serviceWorkers:'block',isMobile:mobile,hasTouch:mobile});
 const page = await context.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 const fixture=await page.evaluate(()=>{
  const c=document.createElement('canvas'); c.width=480;c.height=640;const g=c.getContext('2d');
  const path=new Path2D('M 138 212 C 94 170 91 145 119 120 C 150 96 166 132 195 119 C 224 80 269 96 263 137 C 310 120 339 156 314 188 C 331 219 295 240 257 231 C 245 263 204 248 191 229 C 165 251 126 239 138 212 Z');
  g.fillStyle='rgb(0,170,100)';g.fill(path);g.beginPath();g.ellipse(332,348,45,61,-.7,0,7);g.fill();g.beginPath();g.ellipse(152,390,27,38,.5,0,7);g.fill();const lesion=c.toDataURL();
  g.clearRect(0,0,480,640);g.fillStyle='rgb(96,165,250)';g.fillRect(0,0,480,640);const skin=c.toDataURL();
  g.fillStyle='#dfb995';g.fillRect(0,0,480,640);g.fillStyle='#f7e9dd';g.fill(path);g.beginPath();g.ellipse(332,348,45,61,-.7,0,7);g.fill();g.beginPath();g.ellipse(152,390,27,38,.5,0,7);g.fill();return {lesion,skin,photo:c.toDataURL()};
 });
 const user={id:987654321,username:'synthetic',uid:null,is_active:true,is_admin:false,avatar_url:null,created_at:'2030-01-01'};
 await context.addInitScript(user=>{localStorage.setItem('subskin_token','synthetic-browser-fixture');localStorage.setItem('subskin_user',JSON.stringify(user));localStorage.setItem('subskin_disclaimer_accepted','true')},user);
 const calls=[]; let uploads=0; let fixtureMode='normal'; let completed=true,review=null,storyRequests=0;const storyStatus=Number(process.env.STORY_STATUS || 403);
 await page.route('**/api/**', async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;calls.push({path,method:req.method(),body:req.postData()?.slice(0,2000)});
  let data={};
  if(path.endsWith('/story')) {storyRequests++;assert.equal(JSON.parse(req.postData()).revision,'reviewed-revision');await route.fulfill({status:storyStatus,contentType:'application/json',body:JSON.stringify(storyStatus===200?{theme:'sky',title:'把一片晴空，轻轻握在手心。',source:'ai',revision:'reviewed-revision'}:{detail:'synthetic story unavailable'})});return}
  else if(path==='/api/users/me') data=user;
  else if(path==='/api/vasi/history') data={items:[],total:0};
  else if(path==='/api/vasi/check-photo-quality') data={overall:'good',suggestions:[]};
  else if(path==='/api/vasi/rgb-capabilities') data={protocol:'skin-seg-v2',worker_ready:true};
  else if(path.endsWith('/review')) {review=JSON.parse(req.postData()); data={final_area_percentage:10,measurement:{status:'measured',area_percentage:10,region_count:3,annotation:{protocol:'skin-seg-v2',job_id:'synthetic-job',mask_revision:'reviewed-revision',review_state:'user_reviewed'}}};}
  else if(path.startsWith('/api/vasi/segmentation-jobs')) data={id:'synthetic-job',state:completed?'completed':'queued',stage:completed?'completed':'queued',assessment_id:completed?987654321:null};
  else if(path.includes('/vasi/assess/')) data={id:987654321,record_status:'active',body_site:'left_hand',image_url:fixture.photo,skin_layer_data_url:fixture.skin,lesion_layer_data_url:fixtureMode==='missing' ? null : fixture.lesion,vasi_score:0,area_percentage:12.4,measurement:{version:'photo-v1',status:'measured',scope:'photo',area_percentage:12.4,clinical_vasi_valid:false,region_count:3,reasons:[],annotation:{protocol:'skin-seg-v2',review_state:fixtureMode==='pending'?'pending':'user_reviewed',mask_revision:'synthetic-revision',job_id:'synthetic-job'}},observation:{capture_date:'2030-06-10',label:'左手'}};
  else if(path==='/api/patient-profiles/') data=[{id:1,name:'',is_self:true,relationship:'本人',gender:'女',birth_date:'2000-01-01'},{id:2,name:'',is_self:false,relationship:'孩子',gender:'男',birth_date:'2020-01-01'}];
  else if(path.includes('file-token')) data={token:'synthetic-file',expires_in:300};
  else if(path.includes('/notifications')) data={items:[],unread_count:0};
  else if(path.includes('/categories')||path.includes('/diaries')||path.includes('/tags')) data=[];
  else if(path.includes('/upload')) { uploads++; data={image_url:'/uploads/synthetic-story.png'}; }
  else if(path==='/api/community/posts' && req.method()==='POST') data={id:987654322};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });


 await page.goto('https://staging.subskin.cn/assessment',{waitUntil:'networkidle'});
 await page.getByRole('button',{name:'左手',exact:true}).press('Enter');
 await page.locator('input[type=file]').first().setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:Buffer.from(fixture.photo.split(',')[1],'base64')});
 await page.getByRole('button',{name:'开始分析',exact:true}).click();
 const editor=page.getByRole('region',{name:'核对并调整皮肤和白斑范围'}),canvas=editor.locator('canvas');await canvas.waitFor();
 const confirm=page.getByRole('button',{name:'确认已核对当前皮肤和白斑范围，生成评估结果'});await confirm.waitFor();
 const b=await canvas.boundingBox(),button=await confirm.boundingBox(),x=b.x+b.width*.2,y=b.y+b.height*.8;
 const style=()=>confirm.evaluate(e=>({disabled:e.disabled,opacity:getComputedStyle(e).opacity,bg:getComputedStyle(e).backgroundColor}));
 await confirm.evaluate(async el=>{await Promise.all(el.getAnimations().map(animation=>animation.finished))});
 const baselineStyle=await style(),cdp=mobile?await context.newCDPSession(page):null;
 async function down(x,y){if(cdp)await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});else{await page.mouse.move(x,y);await page.mouse.down()}}
 async function move(x,y){if(cdp)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y}]});else await page.mouse.move(x,y)}
 async function up(){if(cdp)await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});else await page.mouse.up()}
 const frame=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
 await down(x,y);await move(x+20,y);await frame();
 assert.deepEqual(await style(),baselineStyle,'drawing must not dim or disable confirmation');
 for(const tool of ['皮肤','白斑','橡皮'])assert.equal(await page.getByRole('button',{name:tool,exact:true}).isDisabled(),false);
 const ink=await canvas.evaluate(c=>c.toDataURL());await move(button.x+button.width*.5,button.y+button.height*.5);await frame();
 assert.equal(await canvas.evaluate(c=>c.toDataURL()),ink,'moving outside photo cannot paint its edges');
 assert.deepEqual(await style(),baselineStyle);await up();await frame();assert.equal(review,null,'release above confirmation must not submit');
 assert.deepEqual(await canvas.boundingBox(),b);assert.equal(await page.evaluate(()=>getSelection()?.toString()),'');
 // Eraser clears the same displayed pixel immediately even when the preceding tool was lesion.
 const point={x:b.x+b.width*.5,y:b.y+b.height*.8};
 await page.getByRole('button',{name:'白斑',exact:true}).click();await down(point.x,point.y);await up();await frame();
 const pink=await canvas.evaluate(c=>Array.from(c.getContext('2d').getImageData(Math.floor(c.width*.5),Math.floor(c.height*.8),1,1).data));
 await page.getByRole('button',{name:'橡皮',exact:true}).click();await down(point.x,point.y);await up();await frame();
 const erased=await canvas.evaluate(c=>Array.from(c.getContext('2d').getImageData(Math.floor(c.width*.5),Math.floor(c.height*.8),1,1).data));assert.notDeepEqual(erased,pink);
 await page.screenshot({path:out+'/editor-'+width+'.png'});
 await confirm.click();await editor.waitFor({state:'hidden'});
 const poster=page.getByRole('img',{name:/轮廓创意卡：/});await poster.waitFor();assert.equal(await page.getByRole('button',{name:'保存图片',exact:true}).isDisabled(),false);
 if(storyStatus===403)await page.getByText('AI文案尚未授权，轮廓创意仍可保存与分享',{exact:false}).waitFor();
 if(storyStatus===503)await page.getByText('AI文案暂未生成，已保留轮廓创意',{exact:false}).waitFor();
 if(storyStatus===200)await page.getByText('AI 文案',{exact:true}).waitFor();else await page.getByText('模板创意',{exact:true}).waitFor();
 assert.ok(storyRequests>0);assert.equal(await poster.isVisible(),true);assert.equal(await page.getByRole('button',{name:'分享到分享',exact:true}).isDisabled(),false);
 assert.match(await page.getByRole('region',{name:'照片记录结果'}).innerText(),/10%/);
 const samples=await page.evaluate(async review=>{const result=[];for(const src of [review.skin_mask,review.lesion_mask]){const img=new Image();img.src=src;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const ctx=c.getContext('2d');ctx.drawImage(img,0,0);result.push(ctx.getImageData(Math.floor(c.width*.5),Math.floor(c.height*.8),1,1).data[3])}return result},review);assert.deepEqual(samples,[0,0]);
 await poster.screenshot({path:out+'/creative-'+width+'-'+storyStatus+'.png'});
 const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'保存图片',exact:true}).click();await downloadPromise;
 assert.deepEqual(errors,[]);console.log(JSON.stringify({width,height,mobile,storyStatus,passed:true,checks:['controls stable while drawing','outside does not draw or click confirm','no scrolling/selection','eraser restores original and exports empty layers','confirm leads to poster even without AI consent','poster downloadable and shareable']}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
