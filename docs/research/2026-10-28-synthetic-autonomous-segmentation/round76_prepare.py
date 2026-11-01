"""Use generated abstract templates as synthetic intervention shapes."""
import argparse,hashlib,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round74_prepare as base
import round69_prepare as synth


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def template_mask(path):
    gray=np.asarray(Image.open(path).convert('L'));binary=(gray>=200).astype('uint8');count,labels,stats,_=cv2.connectedComponentsWithStats(binary,8)
    if count<2:raise ValueError('empty stencil')
    largest=1+np.argmax(stats[1:,cv2.CC_STAT_AREA]);component=labels==largest;fraction=float(component.mean());other=float((binary.astype(bool)&~component).mean())
    if not .05<=fraction<=.60:raise ValueError('stencil area out of range')
    if component[0].any() or component[-1].any() or component[:,0].any() or component[:,-1].any():raise ValueError('stencil touches edge')
    if other>.01:raise ValueError('too many stray white pixels')
    x,y,w,h,_=map(int,stats[largest]);return component[y:y+h,x:x+w].astype('uint8'),{'size':[int(gray.shape[1]),int(gray.shape[0])],'component_fraction':fraction,'other_white_fraction':other,'bbox':[x,y,w,h]}

def at_location(template,position,radius,sigma,shape):
    side=2*radius+1;h,w=template.shape;scale=side/max(h,w);nw=max(1,round(w*scale));nh=max(1,round(h*scale));mask=cv2.resize(template,(nw,nh),interpolation=cv2.INTER_NEAREST);y,x=position;y0=y-nh//2;x0=x-nw//2
    if y0<0 or x0<0 or y0+nh>shape[0] or x0+nw>shape[1]:raise ValueError('stencil outside frame')
    frame=np.zeros(shape,np.float32);frame[y0:y0+nh,x0:x0+nw]=mask
    return cv2.GaussianBlur(frame,(0,0),sigma)

def run(project,inputs,prior,templates,output):
    reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];doc=json.loads(prior.read_text());assert doc['eligible'] and len(doc['pairs'])==24
    origin_manifest=inputs.parent/'negatives/manifest.json';assert sha(origin_manifest)==doc['source_manifest_sha256'];origin=json.loads(origin_manifest.read_text())
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);masks=[];template_data=[];errors=[]
    for i in range(4):
        path=templates/f'stencil-{i}.png'
        try:
            mask,meta=template_mask(path);masks.append(mask);template_data.append({'id':i,'sha256':sha(path),**meta})
        except Exception as exc:masks.append(None);template_data.append({'id':i,'error':f'{type(exc).__name__}: {exc}'});errors.append({'template':i,'error':str(exc)})
    items=[]
    for i,old in enumerate(doc['pairs']):
        try:
            if any(x is None for x in masks):raise ValueError('template gate failed')
            source=inputs/f"{old['source']}.png";assert sha(source)==origin['sources'][old['source']]['source_sha256'];canvas,core,_=base.core_from_image(source);loc=old['location'];big=at_location(masks[i%4],loc['big_yx'],loc['big_radius'],1.2,core.shape);small=at_location(masks[(i+1)%4],loc['small_yx'],loc['small_radius'],.8,core.shape);alpha=np.maximum(big,small)
            if np.any((alpha>.2)&~core):raise ValueError('outside skin core')
            edited,pos,neg=synth.build_pair(canvas,core,big,small,old['strength']);rgbpos=synth.resized(edited,Image.Resampling.BILINEAR);rgbneg=synth.resized(canvas,Image.Resampling.BILINEAR);ypos=synth.resized(pos,Image.Resampling.NEAREST);yneg=synth.resized(neg,Image.Resampling.NEAREST);counts=[int((synth.resized(x,Image.Resampling.NEAREST)>=.8).sum()) for x in (big,small)]
            if min(counts)<1 or not ((ypos==2)&(yneg==1)).any():raise ValueError('missing resized core')
            files={};key=old['id']
            for role,arr in [('positive',rgbpos),('negative',rgbneg),('positive-mask',ypos),('negative-mask',yneg)]:
                p=output/f'{key}-{role}.png';Image.fromarray(arr).save(p);files[role]={'name':p.name,'sha256':sha(p)}
            if files['negative']['sha256']!=old['files']['negative']['sha256'] or files['negative-mask']['sha256']!=old['files']['negative-mask']['sha256']:raise ValueError('negative mismatch')
            items.append({'id':key,'source':old['source'],'strength':old['strength'],'location':loc,'templates':[i%4,(i+1)%4],'core_pixels_128':counts,'files':files})
        except Exception as exc:errors.append({'case':old['id'],'error':f'{type(exc).__name__}: {exc}'})
    assert before==reg.read_bytes();result={'protocol':'round76-protocol.md','prior_manifest_sha256':sha(prior),'templates':template_data,'pairs':items,'errors':errors,'eligible':len(items)==24 and not errors,'registry_sha256':hashlib.sha256(before).hexdigest()};(output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'pairs':len(items),'errors':errors,'eligible':result['eligible']}),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','inputs','prior','templates','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.inputs,a.prior,a.templates,a.output)
if __name__=='__main__':main()
