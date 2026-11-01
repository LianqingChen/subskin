"""Automatically prompt frozen SAM from synthetic difference, not medical labeling."""
import argparse,hashlib,importlib,json,sys,types
from pathlib import Path
import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from PIL import Image
import round56 as sim
import round58 as partial
import round59 as prior

SOURCES=('test19-hand.png','test21-arm.png','test28-arm.png','test34-hand.png')
METHODS=('difference','sam')
SAM_SHA='ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def prompts(mask,limit=16,padding=8):
    if mask.ndim!=2 or limit<0:raise ValueError('invalid mask or limit')
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'),connectivity=8);order=sorted(range(1,n),key=lambda i:(-int(stats[i,cv2.CC_STAT_AREA]),i));h,w=mask.shape;out=[]
    for idx in order[:limit]:
        x,y,ww,hh,_=map(int,stats[idx]);region=(labels[y:y+hh,x:x+ww]==idx).astype('uint8');distance=cv2.distanceTransform(region,cv2.DIST_L2,5);py,px=np.unravel_index(int(distance.argmax()),distance.shape)
        out.append({'component_id':idx,'point':[x+int(px),y+int(py)],'box':[max(0,x-padding),max(0,y-padding),min(w-1,x+ww-1+padding),min(h-1,y+hh-1+padding)]})
    return labels,out,max(0,len(order)-limit)

def refine_from_masks(strong,unknown,labels,prompts_list,sam_masks):
    if len(prompts_list)!=len(sam_masks):raise ValueError('mask/prompt count mismatch')
    accepted=np.zeros_like(strong,dtype=bool)
    for entry,mask in zip(prompts_list,sam_masks):
        if mask.shape!=strong.shape:raise ValueError('SAM mask shape mismatch')
        accepted|=(labels==entry['component_id'])&mask
    accepted&=strong;new_unknown=(strong|unknown)&~accepted
    assert np.array_equal(accepted|new_unknown,strong|unknown) and not (accepted&new_unknown).any()
    return accepted,new_unknown

class SAMRefiner:
    def __init__(self,package,weights):
        if sha(weights)!=SAM_SHA:raise ValueError('SAM weights hash mismatch')
        package_module=types.ModuleType('segment_anything');package_module.__path__=[str(package)];sys.modules['segment_anything']=package_module
        build=importlib.import_module('segment_anything.build_sam');self.model=build.build_sam_vit_b(checkpoint=str(weights)).eval();encoder=self.model.image_encoder
        pos=encoder.pos_embed.detach().permute(0,3,1,2);encoder.pos_embed=nn.Parameter(F.interpolate(pos,size=(16,16),mode='bicubic',align_corners=False).permute(0,2,3,1),requires_grad=False);encoder.img_size=256;self.model.prompt_encoder.image_embedding_size=(16,16);self.model.prompt_encoder.input_image_size=(256,256)
    def predict(self,image,entries):
        if not entries:return [],[]
        if image.shape!=(256,512,3):raise ValueError('image must be 512x256')
        resized=cv2.resize(image,(256,128),interpolation=cv2.INTER_AREA);tensor=torch.from_numpy(resized.copy()).permute(2,0,1).float()[None]
        coords=torch.tensor([[[e['point'][0]*.5,e['point'][1]*.5]] for e in entries],dtype=torch.float32);labels=torch.ones((len(entries),1),dtype=torch.int64);boxes=torch.tensor([[v*.5 for v in e['box']] for e in entries],dtype=torch.float32)
        with torch.inference_mode():
            features=self.model.image_encoder(self.model.preprocess(tensor));sparse,dense=self.model.prompt_encoder(points=(coords,labels),boxes=boxes,masks=None);low,iou=self.model.mask_decoder(image_embeddings=features,image_pe=self.model.prompt_encoder.get_dense_pe(),sparse_prompt_embeddings=sparse,dense_prompt_embeddings=dense,multimask_output=True);upsampled=self.model.postprocess_masks(low,input_size=(128,256),original_size=(256,512));chosen=iou.argmax(1)
            if not torch.isfinite(upsampled).all() or not torch.isfinite(iou).all():raise ValueError('nonfinite SAM output')
            masks=(upsampled[torch.arange(len(entries)),chosen]>self.model.mask_threshold).cpu().numpy();quality=iou[torch.arange(len(entries)),chosen].cpu().tolist()
        return [m for m in masks],quality

def refine(image,strong,unknown,model):
    labels,entries,dropped=prompts(strong);masks,quality=model.predict(image,entries);new,strong_unknown=refine_from_masks(strong,unknown,labels,entries,masks)
    return new,strong_unknown,{'component_count':len(entries)+dropped,'prompt_count':len(entries),'unprocessed_components':dropped,'predicted_iou':quality}

def choose(cases):
    eligible=[]
    for m in METHODS:
        rows=[x for x in cases if x['method']==m]
        if len(rows)!=24:continue
        if all(x.get('success') and x['thresholds']['control_confirmed_pct']<=1 and x['thresholds']['control_union_pct']<=5 and x['metrics']['confirmed_precision']>=.8 and x['metrics']['covered_big_recall']>=.8 and x['metrics']['covered_small_recall']>=.8 and x['metrics']['confirmed_big_recall']>=.2 and x['metrics']['confirmed_small_recall']>=.2 and x['metrics']['unknown_skin_pct']<=10 for x in rows):eligible.append((min(x['metrics']['covered_small_recall'] for x in rows),-METHODS.index(m),m))
    return max(eligible)[2] if eligible else None

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','images','sam-package','sam-weights','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();cv2.setNumThreads(2);torch.set_num_threads(4);reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True);paths=[a.images/n for n in SOURCES];assert len({sha(x) for x in paths})==4;model=SAMRefiner(a.sam_package,a.sam_weights);cases=[]
    for si,path in enumerate(paths):
        src,shape=sim.base.read(path);core=sim.base.skin_core(src);alpha,big,small,ignore=sim.make_shapes(core);valid=core&~ignore
        for gi,scenario in enumerate(('translation','affine','nonrigid')):
            for ti,strength in enumerate((.12,.28)):
                seed=6000000+si*1000+gi*10+ti;rng=np.random.default_rng(seed);edit=np.clip(src.astype('float32')+alpha[...,None]*strength*(255-src.astype('float32')),0,255).astype('uint8')
                def camera(image,branch):return np.clip(sim.move(image,scenario,branch).astype('float32')+1+rng.normal(0,2,image.shape),0,255).astype('uint8')
                aa0=camera(src,'control');bb0=camera(src,'edited');cc0=camera(src,'edited');ee0=camera(edit,'edited')
                base={'source':path.name,'source_sha256':sha(path),'source_size':shape,'scenario':scenario,'strength':strength,'seed':seed}
                try:
                    aa,ia=sim.align(src,aa0,core,'ecc');bb,ib=sim.align(src,bb0,core,'ecc');cc,ic=sim.align(src,cc0,core,'ecc');ee,ie=sim.align(src,ee0,core,'ecc')
                    if not all(z['success'] for z in (ia,ib,ic,ie)):raise ValueError('alignment gate failed')
                    calibration=sim.base.luma(bb)-sim.base.luma(aa);negative=sim.base.luma(cc)-sim.base.luma(aa);positive=sim.base.luma(ee)-sim.base.luma(aa)
                    cs,cu,t=prior.labels(calibration,negative,core,True);ps,pu,_=prior.labels(calibration,positive,core,True);control=prior.control_stats(cs,cu,core);thresholds={**t,**control}
                    ref={'method':'difference',**base,'success':True,'thresholds':thresholds,'metrics':partial.metrics(ps,pu,big,small,valid,core)};cases.append(ref)
                except Exception as exc:
                    for method in METHODS:cases.append({'method':method,**base,'success':False,'error_type':type(exc).__name__})
                    continue
                try:
                    ncs,ncu,cinfo=refine(cc,cs,cu,model);nps,npu,pinfo=refine(ee,ps,pu,model);newt={**t,**prior.control_stats(ncs,ncu,core)}
                    cases.append({'method':'sam',**base,'success':True,'thresholds':newt,'metrics':partial.metrics(nps,npu,big,small,valid,core),'control_prompts':cinfo,'positive_prompts':pinfo})
                    if si==0 and gi==0 and ti==0:
                        for name,img in [('source',src),('control-c',cc),('intervention',ee),('reference-core',((big|small)*255).astype('uint8')),('difference-confirmed',(ps*255).astype('uint8')),('sam-confirmed',(nps*255).astype('uint8')),('sam-unknown',(npu*255).astype('uint8'))]:Image.fromarray(img).save(a.output_dir/(name+'.png'))
                except Exception as exc:cases.append({'method':'sam',**base,'success':False,'error_type':type(exc).__name__})
        print('completed source',path.name,flush=True)
    assert reg.read_bytes()==before;selected=choose(cases);summary={m:{'cases':sum(x['method']==m for x in cases),'failures':sum(not x.get('success',False) for x in cases if x['method']==m),'eligible':m==selected} for m in METHODS};out={'protocol':'round60-protocol.md','source_sha256':{x.name:sha(x) for x in paths},'sam_sha256':SAM_SHA,'selected_method':selected,'status':'selected_for_further_study' if selected else 'no_eligible_method','summary':summary,'cases':cases,'registry_sha256':hashlib.sha256(before).hexdigest(),'limitations':['SAM nonstandard 256 input','prompts from differential candidates, no human input','program interventions not medical truth','B/C/E share transform class','source aspect ratio stretched','unknown is not normal skin']};(a.output_dir/'results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'selected':selected,'summary':summary},indent=2),flush=True)
if __name__=='__main__':main()
