"""Synthetic-person causal intervention probe; no real clinical labels."""
import argparse,hashlib,importlib.util,json,sys,time
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.nn import functional as F
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r9',HERE/'round9.py');r9=importlib.util.module_from_spec(sp);sp.loader.exec_module(r9);r3=r9.r3;r7=r9.r7


def color_core(rgb):
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV);ycc=cv2.cvtColor(rgb,cv2.COLOR_RGB2YCrCb);h=rgb.shape[0]
    hue=(hsv[:,:,0]<=25)|(hsv[:,:,0]>=160)
    mask=hue&(hsv[:,:,1]>=20)&(hsv[:,:,1]<=220)&(hsv[:,:,2]>=50)&(ycc[:,:,1]>=133)&(ycc[:,:,1]<=180)&(ycc[:,:,2]>=77)&(ycc[:,:,2]<=130)
    mask[:int(h*.65)]=False
    return cv2.erode(mask.astype('uint8'),np.ones((11,11),np.uint8)).astype(bool)


def intervention(rgb,core,seed,strength):
    h,w=rgb.shape[:2];radius=max(6,int(min(h,w)*.02));distance=cv2.distanceTransform(core.astype('uint8'),cv2.DIST_L2,5);positions=np.argwhere(distance>=radius+4)
    if core.sum()<3000 or len(positions)==0:return None
    rng=np.random.default_rng(seed);cy,cx=positions[int(rng.integers(len(positions)))];shape=np.zeros((h,w),np.uint8);cv2.ellipse(shape,(int(cx),int(cy)),(radius,max(4,int(radius*.75))),float(rng.uniform(0,180)),0,360,1,-1)
    alpha=cv2.GaussianBlur(shape.astype('float32'),(0,0),max(1.,radius*.12))*core
    truth=alpha>=.8
    if not truth.any():return None
    img=np.clip(rgb.astype('float32')+alpha[...,None]*strength*(255-rgb.astype('float32')),0,255).astype('uint8')
    return img,truth,{'seed':seed,'strength':strength,'core_pixels':int(truth.sum()),'soft_boundary_pixels':int(((alpha>.2)&(alpha<.8)).sum())}


def candidate_masks(logits,shape):
    logits=F.interpolate(logits,size=shape,mode='bilinear',align_corners=False);prob=torch.softmax(logits,dim=1)[0].cpu().numpy();labels=prob.argmax(0);skin=np.isin(labels,[1,2]);uncertain=(prob.max(0)<.7)&skin
    return {'skin':skin,'lesion':(labels==2)&~uncertain,'uncertain':uncertain,'excluded':np.isin(labels,[3,4])}


def coverage(mask,truth):
    return float((mask&truth).sum()/truth.sum()) if truth.any() else None


def process(rgb,mask_func,funcs):
    png_bytes,hard_check,quality_fn,policy=funcs;data=png_bytes(rgb)
    if hard_check(rgb):return {'outcome':'frame_retake'},None
    try:
        mask,branch=mask_func(rgb);mask,_=quality_fn(rgb,mask);decision=policy(rgb,mask,data,reviewed=False,calibration=None)
        if decision['status']=='retake_required':return {'outcome':'policy_retake','branch':branch},None
        lesion=mask['lesion']&mask['skin']&~mask['excluded'];proposal=(mask['lesion']|mask['uncertain'])&mask['skin']&~mask['excluded']
        return {'outcome':'processed','branch':branch,'policy_status':decision['status'],'blocking_reasons':decision['blocking_reasons'],'lesion_pct_image':float(100*lesion.mean()),'proposal_pct_image':float(100*proposal.mean())},{'lesion':lesion,'proposal':proposal}
    except Exception as exc:return {'outcome':'error','error_type':type(exc).__name__},None


def summarize(rows):
    good=[x for x in rows if x['outcome']=='processed'];mean=lambda xs:float(np.mean(xs)) if xs else None
    return {'total':len(rows),'outcomes':dict(Counter(x['outcome'] for x in rows)),'branches':dict(Counter(x.get('branch','not_applicable') for x in good)),'policies':dict(Counter(x.get('policy_status','unknown') for x in good)),'formal_coverage_mean':mean([x['formal_coverage'] for x in good if x.get('formal_coverage') is not None]),'proposal_coverage_mean':mean([x['proposal_coverage'] for x in good if x.get('proposal_coverage') is not None]),'new_formal_coverage_mean':mean([x['new_formal_coverage'] for x in good if x.get('new_formal_coverage') is not None]),'new_proposal_coverage_mean':mean([x['new_proposal_coverage'] for x in good if x.get('new_proposal_coverage') is not None])}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--project-root',required=True);ap.add_argument('--images',required=True);ap.add_argument('--sam-package',required=True);ap.add_argument('--sam-weights',required=True);ap.add_argument('--output',required=True);ap.add_argument('--preview',required=True);a=ap.parse_args();start=time.time();torch.set_num_threads(4);sys.path.insert(0,a.project_root)
    from web.backend.services.rgb_segmentation.inference import infer_rgb
    from web.backend.services.rgb_segmentation.images import canonical_image,apply_soft_quality,frame_information_lost,png_bytes
    from web.backend.services.rgb_segmentation.policy import measure_rgb
    from web.backend.exceptions import RGBSegmentationError
    funcs=(png_bytes,frame_information_lost,apply_soft_quality,measure_rgb);registry=Path(a.project_root)/'configs/rgb_segmentation_registry.json';reg=registry.read_bytes();assert json.loads(reg)['enabled'] is False;regsha=hashlib.sha256(reg).hexdigest()
    paths=[Path(a.images)/x for x in ('test18-person-medium.png','test18-person-light.png')];hashes=[r3.digest(x) for x in paths];assert len(set(hashes))==2
    arrays=[];input_records=[];preview=Image.new('RGB',(1024,512),'white')
    for j,path in enumerate(paths):
        rgb,_=canonical_image(path.read_bytes(),max_side=512);core=color_core(rgb);overlay=rgb.copy();overlay[core]=(overlay[core]*.45+np.array([0,255,0])*.55).astype('uint8');preview.paste(Image.fromarray(overlay),(j*512,0))
        source={'subject':j,'kind':'source','rgb':rgb,'truth':None,'meta':{'color_core_pixels':int(core.sum())}};arrays.append(source)
        if int(core.sum())<3000:
            input_records.append({'subject':j,'outcome':'unconstructible','color_core_pixels':int(core.sum())});continue
        for k,strength in enumerate((.12,.20,.30)):
            for t in range(4):
                seed=1300000+j*1000+k*10+t;v=intervention(rgb,core,seed,strength)
                if v is None:input_records.append({'subject':j,'outcome':'unconstructible','seed':seed,'strength':strength});continue
                img,truth,meta=v;arrays.append({'subject':j,'kind':'edited','rgb':img,'truth':truth,'meta':meta})
    preview.save(a.preview)
    ref9=json.loads((HERE/'round9-results.json').read_text());ref10=json.loads((HERE/'round10-results.json').read_text());models=[]
    for seed in (0,1):
        for name,folder,file,ref in [('ce','round9-heads',f'arm_and_hand_seed{seed}.pt',next(x for x in ref9['models'] if x['seed']==seed)),('ce_dice','round10-heads',f'ce_dice_seed{seed}.pt',next(x for x in ref10['models'] if x['seed']==seed))]:
            path=HERE/folder/file;sha=r3.digest(path);assert sha==ref['new_head_sha256'];obj=torch.load(path,map_location='cpu',weights_only=True);net=r7.SamHead();net.load_state_dict(obj['state_dict']);net.eval();models.append((f'{name}_{seed}',net,sha))
    tensor=torch.from_numpy(np.stack([cv2.resize(x['rgb'],(64,64),interpolation=cv2.INTER_AREA).transpose(2,0,1).astype('float32')/255 for x in arrays]));enc=r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights));features=r3.encode(enc,tensor);del enc
    names=['current']+[m[0] for m in models];records={name:[] for name in names};baseline={};source_records=[]
    for idx,case in enumerate(arrays):
        rgb=case['rgb'];shape=rgb.shape[:2]
        def current_fn(x):
            masks,meta=infer_rgb(x);return masks,meta.get('source','unknown')
        funcs_by_name={'current':current_fn}
        for name,net,_ in models:
            def fn(x,net=net,idx=idx,shape=shape):
                with torch.inference_mode():mask=candidate_masks(net(tensor[idx:idx+1],features[idx:idx+1]),shape)
                return mask,'offline_candidate_emulation'
            funcs_by_name[name]=fn
        for name,fn in funcs_by_name.items():
            result,mask=process(rgb,fn,funcs);result.update({'subject':case['subject'],'kind':case['kind'],'meta':case['meta']})
            if case['kind']=='source':
                baseline[(case['subject'],name)]=mask;source_records.append({'model':name,**result})
            else:
                if mask is not None:
                    truth=case['truth'];result['formal_coverage']=coverage(mask['lesion'],truth);result['proposal_coverage']=coverage(mask['proposal'],truth);before=baseline.get((case['subject'],name))
                    result['new_formal_coverage']=coverage(mask['lesion']&~before['lesion'],truth) if before is not None else None
                    result['new_proposal_coverage']=coverage(mask['proposal']&~before['proposal'],truth) if before is not None else None
                records[name].append(result)
        if idx%5==0:print('input',idx+1,'/',len(arrays),flush=True)
    assert hashlib.sha256(registry.read_bytes()).hexdigest()==regsha
    import mediapipe
    out={'protocol':'round18-protocol.md','source_hashes':hashes,'registry_sha256':regsha,'registry_enabled':False,'opencv_version':cv2.__version__,'mediapipe_version':getattr(mediapipe,'__version__','unknown'),'torch_version':torch.__version__,'source_records':source_records,'input_failures':input_records,'models':{name:{'overall':summarize(rows),'by_strength':{str(v):summarize([r for r in rows if r['meta']['strength']==v]) for v in (.12,.20,.30)},'by_subject':{str(j):summarize([r for r in rows if r['subject']==j]) for j in (0,1)}} for name,rows in records.items()},'records':records,'limitations':['two AI-generated fictional people, not patients','skin-color heuristic is not ground truth','known programmatic bright intervention, not vitiligo reference','only image-coverage, no clinical precision','candidate uses low-resolution offline emulation','local dependencies differ from production','unreviewed policy withholds measurements'],'elapsed_seconds':round(time.time()-start,2)}
    Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'input_failures':input_records,'source_records':source_records,'models':out['models'],'elapsed_seconds':out['elapsed_seconds']},ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
