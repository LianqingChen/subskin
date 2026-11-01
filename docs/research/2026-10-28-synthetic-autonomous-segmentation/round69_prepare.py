"""Create synthetic paired examples on generator controls; never patient data."""
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round61 as prev


def shape_fields(core,rng):
    safe=cv2.erode(core.astype('uint8'),np.ones((91,91),np.uint8)).astype(bool);points=np.argwhere(safe)
    if len(points)<2:raise ValueError('no safe positions')
    first=points[rng.integers(len(points))];options=points[np.square(points-first).sum(axis=1)>=60**2]
    if len(options)==0:raise ValueError('no separate position')
    second=options[rng.integers(len(options))];big_r=int(rng.integers(28,41));small_r=int(rng.integers(12,17));fields=[]
    for point,radius,sigma in ((first,big_r,1.2),(second,small_r,.8)):
        mask=np.zeros(core.shape,np.uint8);cv2.circle(mask,(int(point[1]),int(point[0])),radius,1,-1);fields.append(cv2.GaussianBlur(mask.astype('float32'),(0,0),sigma))
    return fields,{'big_yx':first.tolist(),'small_yx':second.tolist(),'big_radius':big_r,'small_radius':small_r}

def build_pair(rgb,core,big,small,strength):
    alpha=np.maximum(big,small);edited=np.clip(rgb.astype('float32')+alpha[...,None]*strength*(255-rgb.astype('float32')),0,255).astype('uint8')
    if np.any(edited[alpha==0]!=rgb[alpha==0]):raise ValueError('outside intervention changed')
    negative=np.full(core.shape,255,np.uint8);negative[core]=1;positive=negative.copy();positive[(alpha>.2)&(alpha<.8)&core]=255;positive[(alpha>=.8)&core]=2
    return edited,positive,negative

def resized(im,mode):return np.asarray(Image.fromarray(im).resize((128,128),mode)).copy()

def run(project,inputs,output):
    cv2.setNumThreads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);pro=json.loads((inputs.parent/'input-provenance.json').read_text());hashes={}
    for name in ('leg','hand'):
        for role in ('source','A','B','C'):
            key=f'source-{name}' if role=='source' else f'{name}-{role}';path=inputs/(key+'.png');hashes[key]=prev.sha(path)
            if hashes[key]!=pro[key]['sha256']:raise ValueError('input hash mismatch')
    rng=np.random.default_rng(6905);items=[]
    for name in ('leg','hand'):
        source,_=prev.read_letterbox(inputs/f'source-{name}.png');core=prev.skin_core(source)
        for role in ('A','B','C'):
            img,meta=prev.read_letterbox(inputs/f'{name}-{role}.png');base,state=prev.align(source,img,core)
            if not state['success']:raise ValueError('control alignment')
            for i in range(16):
                (big,small),location=shape_fields(core,rng);strength=(.06,.12,.28,.42)[i%4];edited,pos,neg=build_pair(base,core,big,small,strength)
                rgbpos=resized(edited,Image.Resampling.BILINEAR);rgbneg=resized(base,Image.Resampling.BILINEAR);ypos=resized(pos,Image.Resampling.NEAREST);yneg=resized(neg,Image.Resampling.NEAREST);bigsmall=[resized(x,Image.Resampling.NEAREST) for x in (big,small)];counts=[int((x>=.8).sum()) for x in bigsmall]
                if min(counts)<1 or not np.any((ypos==2)&(yneg==1)):raise ValueError('core vanished')
                key=f'{name}-{role}-{i:02d}';files={}
                for label,array in [('positive',rgbpos),('negative',rgbneg),('positive-mask',ypos),('negative-mask',yneg)]:
                    path=output/f'{key}-{label}.png';Image.fromarray(array).save(path);files[label]={'name':path.name,'sha256':prev.sha(path)}
                items.append({'id':key,'source':name,'control':role,'strength':strength,'location':location,'core_pixels_128':counts,'control_alignment':state,'files':files})
        print(name,'generated',flush=True)
    if len(items)!=96:raise ValueError('wrong pair count')
    assert before==reg.read_bytes();out={'protocol':'round69-protocol.md','seed':6905,'input_sha256':hashes,'pairs':items,'registry_sha256':hashlib.sha256(before).hexdigest()};(output/'manifest.json').write_text(json.dumps(out,indent=2)+'\n');print('pairs',len(items),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','inputs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.inputs,a.output)
if __name__=='__main__':main()
