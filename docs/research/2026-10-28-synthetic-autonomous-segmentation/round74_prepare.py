"""Produce weak negative cores from fictional generated cyan-screen images."""
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

NAMES=('light-arm','dark-arm','light-hand','dark-hand')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def core_from_image(path):
    with Image.open(path) as im:
        im=im.convert('RGB');w,h=im.size;corners=np.array([im.getpixel(p) for p in ((0,0),(w-1,0),(0,h-1),(w-1,h-1))],dtype='float32')
        if not ((corners[:,0]<130)&(corners[:,1]>150)&(corners[:,2]>150)).all():raise ValueError('corner color invalid')
        if np.max(np.linalg.norm(corners[:,None]-corners[None,:],axis=2))>45:raise ValueError('corner colors inconsistent')
        background=np.median(corners,axis=0);scale=512/max(w,h);nw,nh=round(w*scale),round(h*scale);scaled=np.asarray(im.resize((nw,nh),Image.Resampling.LANCZOS));canvas=np.empty((512,512,3),np.uint8);canvas[:]=background.astype('uint8');x=(512-nw)//2;y=(512-nh)//2;canvas[y:y+nh,x:x+nw]=scaled
    d=np.linalg.norm(canvas.astype('float32')-background,axis=2);nonbackground=(d>45).astype('uint8');core=cv2.erode(nonbackground,np.ones((7,7),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
    if not .1<core.mean()<.9:raise ValueError('core coverage invalid')
    return canvas,core,{'size':[w,h],'corners':corners.tolist(),'background_median':background.tolist(),'core_fraction':float(core.mean())}

def run(project,inputs,output):
    reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);result={}
    for name in NAMES:
        source=inputs/(name+'.png');row={'source_sha256':sha(source) if source.exists() else None,'status':'error'}
        try:
            if not source.exists():raise ValueError('missing source')
            canvas,core,info=core_from_image(source);label=np.full(core.shape,255,np.uint8);label[core]=1;rgb=np.asarray(Image.fromarray(canvas).resize((128,128),Image.Resampling.BILINEAR));mask=np.asarray(Image.fromarray(label).resize((128,128),Image.Resampling.NEAREST));
            if not np.any(mask==1):raise ValueError('empty resized core')
            for suffix,arr in [('image',rgb),('mask',mask),('core512',(core*255).astype('uint8'))]:Image.fromarray(arr).save(output/f'{name}-{suffix}.png')
            row.update(status='ok',**info,files={suffix:{'file':f'{name}-{suffix}.png','sha256':sha(output/f'{name}-{suffix}.png')} for suffix in ('image','mask','core512')})
        except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
        result[name]=row
    assert before==reg.read_bytes();doc={'protocol':'round74-protocol.md','sources':result,'eligible':all(x['status']=='ok' for x in result.values()),'assumption':'generated noncyan core presumed normal; not verified truth','registry_sha256':hashlib.sha256(before).hexdigest()};(output/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');print(json.dumps({'eligible':doc['eligible'],'statuses':{k:v['status'] for k,v in result.items()}}),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','inputs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.inputs,a.output)
if __name__=='__main__':main()
