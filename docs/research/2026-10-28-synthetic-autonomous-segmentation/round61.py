"""Diagnose image-generator edit drift; results are not training labels."""
import argparse,hashlib,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round59 as stratify

CONTROL_PROMPT='Reproduce the provided fictional synthetic skin image as an unaltered control. Preserve the exact skin shape, position, surface texture, lighting, and solid cyan background. Do not add patches, scars, text, or a watermark. Keep the same aspect ratio and framing.'
EDIT_PROMPT='Edit the provided fictional synthetic skin image by adding one irregular pale depigmented skin area and a separate small satellite area, while preserving all other skin texture, anatomy, lighting, framing, and solid cyan background. No text or watermark. Keep the same aspect ratio. Entirely fictional; no real patient.'
ROLES=('A','B','C','E')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def read_letterbox(path):
    with Image.open(path) as im:
        im=im.convert('RGB');w,h=im.size;scale=512/max(w,h);nw,nh=max(1,round(w*scale)),max(1,round(h*scale));arr=np.asarray(im.resize((nw,nh),Image.Resampling.LANCZOS))
    canvas=np.empty((512,512,3),np.uint8);canvas[:]=[0,180,250];y=(512-nh)//2;x=(512-nw)//2;canvas[y:y+nh,x:x+nw]=arr
    return canvas,{'size':[w,h],'resized':[nw,nh],'offset':[x,y],'aspect':w/h}

def native_corners_cyan(path):
    with Image.open(path) as im:
        rgb=im.convert('RGB');w,h=rgb.size;points=[rgb.getpixel(xy) for xy in ((0,0),(w-1,0),(0,h-1),(w-1,h-1))]
    return all(r<85 and g>120 and b>125 and b>1.2*r for r,g,b in points)

def acceptable_aspect(source_aspect,output_aspect):return abs(output_aspect/source_aspect-1)<=.01

def skin_core(src):
    z=src.astype('int16');cyan=(z[:,:,0]<85)&(z[:,:,1]>120)&(z[:,:,2]>125)&(z[:,:,2]>z[:,:,0]*1.2)
    if not all((cyan[0,0],cyan[0,-1],cyan[-1,0],cyan[-1,-1])):raise ValueError('source corners not cyan')
    core=cv2.erode((~cyan).astype('uint8'),np.ones((7,7),np.uint8)).astype(bool)
    if not .1<core.mean()<.9:raise ValueError('source skin coverage out of range')
    return core

def align(src,img,core):
    ref=cv2.cvtColor(src,cv2.COLOR_RGB2GRAY).astype('float32')/255;moving=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY).astype('float32')/255;warp=np.eye(2,3,dtype='float32')
    try:
        corr,warp=cv2.findTransformECC(ref,moving,warp,cv2.MOTION_AFFINE,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,250,1e-6),core.astype('uint8'),5)
        determinant=float(np.linalg.det(warp[:,:2]));ok=bool(np.isfinite(warp).all() and .7<=determinant<=1.3 and abs(warp[0,2])<=102.4 and abs(warp[1,2])<=102.4)
        out=cv2.warpAffine(img,warp,(512,512),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,180,250))
        return out,{'success':ok,'correlation':float(corr),'determinant':determinant,'matrix':warp.tolist()}
    except cv2.error as exc:return img,{'success':False,'error':str(exc).split('\n')[0]}

def analyze(source,outputs):
    
    if not native_corners_cyan(source):raise ValueError('native source corners not cyan')
    src,info=read_letterbox(source);core=skin_core(src);data={'source':{'file':source.name,'sha256':sha(source),**info},'core_fraction':float(core.mean()),'inputs':{},'alignments':{}}
    aligned={}
    for role in ROLES:
        path=outputs[role];img,metadata=read_letterbox(path);data['inputs'][role]={'file':path.name,'sha256':sha(path),**metadata}
        if not acceptable_aspect(info['aspect'],metadata['aspect']):data.update(status='rejected_aspect',failed_role=role);return data,None
        aligned[role],state=align(src,img,core);data['alignments'][role]=state
        if not state['success']:data.update(status='rejected_alignment',failed_role=role);return data,None
    lum=stratify.sim.base.luma
    calibration=lum(aligned['B'])-lum(aligned['A']);negative=lum(aligned['C'])-lum(aligned['A']);positive=lum(aligned['E'])-lum(aligned['A'])
    strong,unknown,thresholds=stratify.labels(calibration,positive,core,True);ns,nu,_=stratify.labels(calibration,negative,core,True);thresholds.update(stratify.control_stats(ns,nu,core));confirmed_pct=float(100*(strong&core).sum()/core.sum());unknown_pct=float(100*(unknown&core).sum()/core.sum());gates={'control_confirmed_at_most_1pct':thresholds['control_confirmed_pct']<=1,'control_union_at_most_5pct':thresholds['control_union_pct']<=5,'edited_unknown_at_most_10pct':unknown_pct<=10,'edited_confirmed_nonempty_at_most_30pct':0<confirmed_pct<=30};data.update(status='passes_drift_screen_only' if all(gates.values()) else 'rejected_drift_screen',thresholds=thresholds,edited_confirmed_pct=confirmed_pct,edited_unknown_pct=unknown_pct,gates=gates,not_a_training_label=True)
    return data,{'source':src,'control-a-aligned':aligned['A'],'control-c-aligned':aligned['C'],'edited-aligned':aligned['E'],'confirmed':(strong*255).astype('uint8'),'unknown':(unknown*255).astype('uint8')}

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','inputs','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();cv2.setNumThreads(2);reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True);results={}
    for source in ('leg','hand'):
        files={role:a.inputs/f'{source}-{role}.png' for role in ROLES};sourcefile=a.inputs/f'source-{source}.png'
        if not sourcefile.exists() or any(not f.exists() for f in files.values()):results[source]={'status':'missing_input','missing':[x for x in (['source'] if not sourcefile.exists() else [])+[k for k,v in files.items() if not v.exists()]]};continue
        try:
            outcome,visuals=analyze(sourcefile,files);results[source]=outcome
            if visuals:
                folder=a.output_dir/source;folder.mkdir()
                for name,image in visuals.items():Image.fromarray(image).save(folder/(name+'.png'))
        except Exception as exc:results[source]={'status':'error','error_type':type(exc).__name__}
    assert reg.read_bytes()==before
    result={'protocol':'round61-protocol.md','control_prompt':CONTROL_PROMPT,'edit_prompt':EDIT_PROMPT,'results':results,'registry_sha256':hashlib.sha256(before).hexdigest(),'used_for_training':False,'limitations':['no independent lesion ground truth','generated controls may drift','ECC may absorb changes','drift screen is not clinical accuracy']}
    (a.output_dir/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v['status'] for k,v in results.items()},indent=2),flush=True)
if __name__=='__main__':main()
