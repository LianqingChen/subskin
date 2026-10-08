// Browser regression against staging; all API traffic uses synthetic fixtures.
const {chromium} = require(process.env.SUBSKIN_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'); const assert = require('node:assert/strict');
const out = process.env.SUBSKIN_BRUSH_QA_OUT || '/tmp/subskin-brush-qa'; fs.mkdirSync(out,{recursive:true});
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
 const calls=[]; let uploads=0; let fixtureMode='normal'; let completed=false,review=null;
 await page.route('**/api/**', async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;calls.push({path,method:req.method(),body:req.postData()?.slice(0,2000)});
  let data={};
  if(path==='/api/users/me') data=user;
  else if(path==='/api/vasi/history') data={items:[],total:0};
  else if(path==='/api/vasi/check-photo-quality') data={overall:'good',suggestions:[]};
  else if(path==='/api/vasi/rgb-capabilities') data={protocol:'skin-seg-v2',worker_ready:true};
  else if(path.endsWith('/review')) {review=JSON.parse(req.postData()); data={final_area_percentage:10,measurement:{status:'measured',annotation:{protocol:'skin-seg-v2',review_state:'user_reviewed'}}};}
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
 const start=page.getByRole('button',{name:'开始分析',exact:true});await start.waitFor();
 assert.equal(await page.getByText('更多设置',{exact:true}).count(),0);
 await page.screenshot({path:out+'/capture-'+width+'.png'});
 await start.click();const cancel=page.getByRole('button',{name:'取消分析',exact:true});await cancel.waitFor();
 const style=await cancel.evaluate(el=>({height:el.getBoundingClientRect().height,border:getComputedStyle(el).borderTopWidth,weight:getComputedStyle(el).fontWeight}));
 assert.equal(style.border,'1px');assert.equal(style.weight,'500');assert.ok(style.height<=44);
 await page.screenshot({path:out+'/analysis-'+width+'.png'});
 await cancel.click();await start.waitFor();completed=true;await start.click();
 const canvas=page.getByRole('img',{name:'照片标注：浅蓝为皮肤，浅粉为白斑'});await canvas.waitFor();
 const cdp=mobile?await context.newCDPSession(page):null;
 const bounds=await canvas.boundingBox();assert.ok(bounds.height>100&&bounds.y>=0&&bounds.y+bounds.height<=height);
 async function stroke(tool,y=.85) {
   await page.getByRole('button',{name:tool,exact:true}).click();
   const b=await canvas.boundingBox(),x=b.x+b.width*.2,cy=b.y+b.height*y,dx=b.width*.6;
   if(mobile){
     await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y:cy}]});
     for(let i=1;i<=12;i++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x+dx*i/12,y:cy}]});
     await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
   }else{await page.mouse.move(x,cy);await page.mouse.down();await page.mouse.move(x+dx,cy,{steps:12});await page.mouse.up();}
   await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   assert.equal(page.url(),'https://staging.subskin.cn/assessment');
   assert.deepEqual(await canvas.boundingBox(),b,'drawing must not scroll or resize the photo');
   assert.equal(await page.evaluate(()=>getSelection()?.toString()),'','drawing must not select page content');
 }
 async function pixel(y=.85){return canvas.evaluate((c,y)=>Array.from(c.getContext('2d').getImageData(Math.floor(c.width*.5),Math.floor(c.height*y),1,1).data),y);}
 const blue=await pixel();await stroke('白斑');const pink=await pixel();assert.notDeepEqual(pink,blue);
 await stroke('皮肤');assert.deepEqual(await pixel(),blue);
 await stroke('橡皮');const original=await pixel();assert.notDeepEqual(original,blue);assert.notDeepEqual(original,pink);
 await stroke('白斑');assert.deepEqual(await pixel(),pink);
 await stroke('橡皮');assert.deepEqual(await pixel(),original);
 await stroke('白斑',.9);await stroke('皮肤',.75);await stroke('橡皮',.75);
 await page.getByRole('button',{name:'粗细',exact:false}).click();await page.getByRole('slider',{name:'画笔和橡皮粗细',exact:true}).fill('32');
 await page.getByRole('button',{name:'粗细',exact:false}).click();
 await page.screenshot({path:out+'/editor-'+width+'.png'});
 await page.evaluate(()=>document.documentElement.classList.add('dark'));await page.screenshot({path:out+'/editor-dark-'+width+'.png'});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.getByRole('button',{name:'确认已核对当前皮肤和白斑范围，生成评估结果',exact:true}).click();
 await page.getByRole('region',{name:'核对并调整皮肤和白斑范围',exact:true}).waitFor({state:'hidden'});
 assert.ok(review,'confirmation submits edited masks');assert.equal(review.acknowledged,true);
 const maskSamples=await page.evaluate(async review=>{
  async function read(src){const img=new Image();img.src=src;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const g=c.getContext('2d');g.drawImage(img,0,0);return [.75,.85,.9].map(y=>g.getImageData(Math.floor(c.width*.5),Math.floor(c.height*y),1,1).data[3]);}
  return {skin:await read(review.skin_mask),lesion:await read(review.lesion_mask)};
 },review);
 assert.deepEqual(maskSamples,{skin:[0,0,255],lesion:[0,0,255]});assert.deepEqual(errors,[]);
 console.log(JSON.stringify({width,height,mobile,passed:true,checks:['compact capture','slim cancel and retry','skin/lesion replacement','skin and lesion erasing','no scrolling or text selection','brush width','dark layout','exported masks match visible strokes'],maskSamples}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
