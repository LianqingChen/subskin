"""Frozen synthetic-model assessment on new fictional sources; research only."""
import argparse, hashlib, json, sys
from pathlib import Path
import cv2
import numpy as np
import torch
import round61 as prev
import round62 as prior
import round66 as scoring
import round71_shapes as synth

NAMES=('light-arm','dark-arm','light-hand','dark-hand')
MODELS=(('tuned',19,69),('tuned',43,69),('weak',19,74),('weak',43,74))
EXPOSURES=(.8,1.,1.2)
STRENGTHS=(.06,.12,.28)

def expose(rgb,factor):return np.clip(rgb.astype('float32')*factor,0,255).astype('uint8')

def imaging_stats(img,base,core,big,small):
    truth=(big>=.8)|(small>=.8);saturation=np.any(img==255,axis=2)
    return {'skin_channel_saturation_pct':float(100*saturation[core].mean()),'core_no_rgb_change_pct':float(100*np.all(img==base,axis=2)[truth].mean())}

def prepare_source(name,inputs,rng):
    sp=inputs/f'source-{name}.png';cp=inputs/f'{name}-C.png'
    if not sp.exists() or not cp.exists():raise ValueError('missing source or control')
    if not prev.native_corners_cyan(sp):raise ValueError('source corners not cyan')
    src,meta=prev.read_letterbox(sp);core=prev.skin_core(src);control,cmeta=prev.read_letterbox(cp)
    if not prev.acceptable_aspect(meta['aspect'],cmeta['aspect']):raise ValueError('control aspect mismatch')
    aligned,state=prev.align(src,control,core)
    if not state['success']:raise ValueError('control alignment failed')
    positions=[]
    for i in range(2):
        try:
            (big,small),loc=synth.shape_fields(core,rng);positions.append({'big':big,'small':small,'location':loc,'error':None})
        except Exception as exc:positions.append({'error':f'{type(exc).__name__}: {exc}'})
    return {'core':core,'control':aligned,'positions':positions,'source_info':meta,'control_info':cmeta,'alignment':state}

def run(project,research,inputs,output):
    sys.path.insert(0,str(project));from ml.rgb_segmentation.evaluate import predict
    cv2.setNumThreads(2);torch.set_num_threads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(7005);prepared={};source_info={};hashes={}
    for name in NAMES:
        hashes[name]={role:prev.sha(p) if p.exists() else None for role,p in [('source',inputs/f'source-{name}.png'),('control',inputs/f'{name}-C.png')]}
        try:
            z=prepare_source(name,inputs,rng);prepared[name]=z;source_info[name]={'status':'ok','source':z['source_info'],'control':z['control_info'],'alignment':z['alignment'],'locations':[{'location':x.get('location'),'error':x['error']} for x in z['positions']]}
        except Exception as exc:prepared[name]=None;source_info[name]={'status':'error','error':f'{type(exc).__name__}: {exc}'}
    models={};rows=[]
    for kind,seed,num in MODELS:
        label=f'{kind}-{seed}';folder=(research/'round69-artifacts'/label) if kind=='tuned' else (Path('/tmp/subskin-round74')/label);weights=folder/'baseline.pt';meta=json.loads((folder/'summary.json').read_text());h=prev.sha(weights)
        if h!=meta['model_sha256']:raise ValueError('weights hash mismatch')
        net=torch.jit.load(str(weights),map_location='cpu').eval();models[label]={'sha256':h,'status':meta['status']}
        for name in NAMES:
            z=prepared[name]
            for exposure in EXPOSURES:
                row={'model':label,'source':name,'kind':'negative','exposure':exposure,'success':False}
                try:
                    if z is None:raise ValueError('source rejected: '+source_info[name]['error'])
                    rgb=expose(z['control'],exposure);pred=predict(net,rgb)==2;row.update(success=True,metrics=scoring.score(pred,z['core']),skin_channel_saturation_pct=float(100*np.any(rgb==255,axis=2)[z['core']].mean()));directory=output/label;directory.mkdir(exist_ok=True);stem=f'{name}-negative-e{exposure:.1f}.png';from PIL import Image;Image.fromarray((pred*255).astype('uint8')).save(directory/stem);row['prediction_sha256']=prev.sha(directory/stem)
                except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                rows.append(row)
            for position in range(2):
                for strength in STRENGTHS:
                    for exposure in EXPOSURES:
                        row={'model':label,'source':name,'kind':'positive','position':position,'strength':strength,'exposure':exposure,'success':False}
                        try:
                            if z is None:raise ValueError('source rejected: '+source_info[name]['error'])
                            pos=z['positions'][position]
                            if pos['error']:raise ValueError('position rejected: '+pos['error'])
                            big,small=pos['big'],pos['small'];alpha=np.maximum(big,small);original=z['control'];edited=prior.synthesize(original,alpha,strength);rgb=expose(edited,exposure);negative=expose(original,exposure);core=z['core'];truth=(alpha>=.5)&core;b=(big>=.8)&core;s=(small>=.8)&core;pred=predict(net,rgb)==2
                            row.update(success=True,metrics=scoring.score(pred,core,truth,b,s),imaging=imaging_stats(rgb,negative,core,big,small));directory=output/label;directory.mkdir(exist_ok=True);stem=f'{name}-p{position}-s{strength:.2f}-e{exposure:.1f}.png';from PIL import Image;Image.fromarray((pred*255).astype('uint8')).save(directory/stem);row['prediction_sha256']=prev.sha(directory/stem)
                        except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                        rows.append(row)
        print(label,'complete',flush=True)
    assert len(rows)==336 and reg.read_bytes()==before
    result={'protocol':'round74-protocol.md','input_sha256':hashes,'sources':source_info,'models':models,'rows':rows,'registry_sha256':hashlib.sha256(before).hexdigest(),'training':False,'limitations':['synthetic alpha not clinical truth','positive and negative share C image','exposure is numeric sRGB multiplier','generated source may have artifacts','unknown pretraining provenance']};(output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'rows':len(rows),'errors':sum(not r['success'] for r in rows),'sources':{k:v['status'] for k,v in source_info.items()}}),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','research','inputs','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.research,a.inputs,a.output)
if __name__=='__main__':main()
