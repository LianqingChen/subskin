"""Evaluate frozen models on held-out generated synthetic silhouettes."""
import argparse,hashlib,json,sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import torch
import round61 as prev
import round62 as prior
import round66 as scoring
import round71 as exp
import round76_prepare as stencil

MODELS=(('tuned',19,69),('tuned',43,69),('paired',19,75),('paired',43,75),('organic',19,76),('organic',43,76))

def boundary_f1(pred,truth,core):
    a=(pred&core).astype('uint8');b=(truth&core).astype('uint8');kernel=np.ones((3,3),np.uint8)
    ae=a.astype(bool)&~cv2.erode(a,kernel,borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool);be=b.astype(bool)&~cv2.erode(b,kernel,borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
    if not ae.any() or not be.any():return 0.
    tol=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5));near_b=cv2.dilate(be.astype('uint8'),tol).astype(bool);near_a=cv2.dilate(ae.astype('uint8'),tol).astype(bool);precision=float((ae&near_b).sum()/ae.sum());recall=float((be&near_a).sum()/be.sum());return 2*precision*recall/(precision+recall) if precision+recall else 0.

def run(project,research,inputs,templates,output):
    sys.path.insert(0,str(project));from ml.rgb_segmentation.evaluate import predict
    torch.set_num_threads(2);cv2.setNumThreads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);old71=json.loads((research/'round71-artifacts/completed/results.json').read_text());old75=json.loads((research/'round75-artifacts/probe/results.json').read_text());old76=json.loads((research/'round76-artifacts/probe/results.json').read_text());past_reports={'tuned':old71,'paired':old75,'organic':old76};training_templates=json.loads((research/'round76-artifacts/template-provenance.json').read_text());forbidden={x['sha256'] for x in training_templates.values()};masks=[];template_data=[]
    for i in range(2):
        p=templates/f'stencil-{i}.png'
        try:
            h=prev.sha(p)
            if h in forbidden:raise ValueError('template duplicates training')
            mask,meta=stencil.template_mask(p);masks.append(mask);template_data.append({'id':i,'sha256':h,**meta,'status':'ok'})
        except Exception as exc:masks.append(None);template_data.append({'id':i,'status':'error','error':f'{type(exc).__name__}: {exc}'})
    rng=np.random.default_rng(7005);sources={};references={};info={}
    for name in exp.NAMES:
        for role,p in [('source',inputs/f'source-{name}.png'),('control',inputs/f'{name}-C.png')]:
            if (prev.sha(p) if p.exists() else None)!=old71['input_sha256'][name][role]:raise ValueError('input hash mismatch')
        try:
            z=exp.prepare_source(name,inputs,rng);expected=old71['sources'][name]
            if expected['status']!='ok':raise ValueError('source state mismatch')
            for i,pos in enumerate(z['positions']):
                if pos['error']!=expected['locations'][i]['error'] or pos.get('location')!=expected['locations'][i].get('location'):raise ValueError('position mismatch')
                if pos['error'] or any(x is None for x in masks):continue
                try:
                    loc=pos['location'];big=stencil.at_location(masks[0],loc['big_yx'],loc['big_radius'],1.2,z['core'].shape);small=stencil.at_location(masks[1],loc['small_yx'],loc['small_radius'],.8,z['core'].shape);alpha=np.maximum(big,small);core=z['core']
                    if np.any((alpha>.2)&~core) or not (big>=.8).any() or not (small>=.8).any():raise ValueError('invalid reference extent')
                    references[(name,i)]={'big':big,'small':small,'alpha':alpha};folder=output/'references';folder.mkdir(exist_ok=True)
                    for suffix,mask in [('full',(alpha>=.5)&core),('big',(big>=.8)&core),('small',(small>=.8)&core)]:
                        p=folder/f'{name}-p{i}-{suffix}.png';Image.fromarray((mask*255).astype('uint8')).save(p)
                except Exception as exc:references[(name,i)]={'error':f'{type(exc).__name__}: {exc}'}
            sources[name]=z;info[name]={'status':'ok','positions':[{'location':x.get('location'),'error':x['error']} for x in z['positions']]}
        except Exception as exc:
            if old71['sources'][name]['status']!='error':raise
            sources[name]=None;info[name]={'status':'error','error':f'{type(exc).__name__}: {exc}'}
    rows=[];models={};mismatches=[]
    for kind,seed,num in MODELS:
        label=f'{kind}-{seed}';folder=research/f'round{num}-artifacts'/label;weights=folder/'baseline.pt';meta=json.loads((folder/'summary.json').read_text());h=prev.sha(weights)
        if h!=meta['model_sha256']:raise ValueError('weight hash mismatch')
        net=torch.jit.load(str(weights),map_location='cpu').eval();models[label]={'sha256':h,'status':meta['status']}
        for name in exp.NAMES:
            z=sources[name]
            for exposure in exp.EXPOSURES:
                row={'model':label,'source':name,'kind':'negative','exposure':exposure,'success':False}
                try:
                    if z is None:raise ValueError('source rejected')
                    rgb=exp.expose(z['control'],exposure);pred=predict(net,rgb)==2;met=scoring.score(pred,z['core']);row.update(success=True,metrics=met);matches=[x for x in past_reports[kind]['rows'] if x['model']==label and x['source']==name and x['kind']=='negative' and x['exposure']==exposure]
                    if len(matches)!=1 or matches[0]['metrics']!=met:mismatches.append({'model':label,'source':name,'exposure':exposure})
                    d=output/label;d.mkdir(exist_ok=True);p=d/f'{name}-negative-e{exposure:.1f}.png';Image.fromarray((pred*255).astype('uint8')).save(p);row['prediction_sha256']=prev.sha(p)
                except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                rows.append(row)
            for position in range(2):
                for strength in exp.STRENGTHS:
                    for exposure in exp.EXPOSURES:
                        row={'model':label,'source':name,'kind':'positive','position':position,'strength':strength,'exposure':exposure,'success':False}
                        try:
                            if z is None:raise ValueError('source rejected')
                            if any(x is None for x in masks):raise ValueError('template gate failed')
                            if z['positions'][position]['error']:raise ValueError('original position rejected')
                            ref=references.get((name,position))
                            if not ref or 'error' in ref:raise ValueError('reference rejected')
                            big,small,alpha=ref['big'],ref['small'],ref['alpha'];core=z['core'];original=z['control'];img=exp.expose(prior.synthesize(original,alpha,strength),exposure);negative=exp.expose(original,exposure);truth=(alpha>=.5)&core;b=(big>=.8)&core;s=(small>=.8)&core;pred=predict(net,img)==2;met=scoring.score(pred,core,truth,b,s);met['boundary_f1_2px']=boundary_f1(pred,truth,core);row.update(success=True,metrics=met,imaging=exp.imaging_stats(img,negative,core,big,small));d=output/label;d.mkdir(exist_ok=True);p=d/f'{name}-p{position}-s{strength:.2f}-e{exposure:.1f}.png';Image.fromarray((pred*255).astype('uint8')).save(p);row['prediction_sha256']=prev.sha(p)
                        except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                        rows.append(row)
        print(label,'complete',flush=True)
    assert len(rows)==504 and reg.read_bytes()==before
    result={'protocol':'round77-protocol.md','template_data':template_data,'sources':info,'models':models,'rows':rows,'negative_baseline_reproduced':not mismatches,'negative_mismatches':mismatches,'registry_sha256':hashlib.sha256(before).hexdigest(),'training':False,'limitations':['previously observed synthetic sources','new shapes share generator with training','synthetic alpha not medical truth','same source yields correlated cases']};(output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'rows':len(rows),'failures':sum(not x['success'] for x in rows),'negative_baseline_reproduced':not mismatches,'templates':[x['status'] for x in template_data]}),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','research','inputs','templates','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.research,a.inputs,a.templates,a.output)
if __name__=='__main__':main()
