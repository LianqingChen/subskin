"""Evaluate known interventions on generator-produced control drift; research only."""
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round56 as sim
import round58 as scoring
import round59 as stratify
import round61 as previous

ROLES=('A','B','C')
STRENGTHS=(.06,.12,.28)
PLACEMENTS=('original','mirror')

def warp_alpha(alpha, matrix):
    return cv2.warpAffine(alpha.astype('float32'), np.asarray(matrix,dtype='float32'), (512,512), flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

def synthesize(image, alpha, strength):
    return np.clip(image.astype('float32')+alpha[...,None]*strength*(255-image.astype('float32')),0,255).astype('uint8')

def gates(row):
    t,m=row['thresholds'],row['metrics']
    return {'control_confirmed':t['control_confirmed_pct']<=1,'control_union':t['control_union_pct']<=5,'precision':m['confirmed_precision']>=.8,'big_confirmed':m['confirmed_big_recall']>=.2,'small_confirmed':m['confirmed_small_recall']>=.2,'big_covered':m['covered_big_recall']>=.8,'small_covered':m['covered_small_recall']>=.8,'unknown':m['unknown_skin_pct']<=10}

def run(inputs,output,project):
    cv2.setNumThreads(2); reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('output not empty')
    output.mkdir(parents=True,exist_ok=True); rows=[]; provenance={}
    for name in ('leg','hand'):
        paths={'source':inputs/f'source-{name}.png',**{role:inputs/f'{name}-{role}.png' for role in ROLES}}
        provenance[name]={role:previous.sha(path) for role,path in paths.items()}
        try:
            if not previous.native_corners_cyan(paths['source']):raise ValueError('source corners')
            src,info=previous.read_letterbox(paths['source']);core=previous.skin_core(src); aligned={}; alignment={}; raw={}
            for role in ROLES:
                raw[role],metadata=previous.read_letterbox(paths[role])
                if not previous.acceptable_aspect(info['aspect'],metadata['aspect']):raise ValueError('aspect')
                aligned[role],alignment[role]=previous.align(src,raw[role],core)
                if not alignment[role]['success']:raise ValueError('control alignment')
            alpha,big,small,_=sim.make_shapes(core)
            # Keep two separate alpha fields so their references remain identifiable.
            big_alpha=np.where(cv2.dilate(big.astype('uint8'),np.ones((9,9),np.uint8)).astype(bool),alpha,0).astype('float32')
            small_alpha=np.where(cv2.dilate(small.astype('uint8'),np.ones((9,9),np.uint8)).astype(bool),alpha,0).astype('float32')
            cal=sim.base.luma(aligned['B'])-sim.base.luma(aligned['A']);neg=sim.base.luma(aligned['C'])-sim.base.luma(aligned['A'])
            ns,nu,_=stratify.labels(cal,neg,core,True); control=stratify.control_stats(ns,nu,core);failure=None
        except Exception as exc:failure=f'{type(exc).__name__}: {exc}'
        for placement in PLACEMENTS:
            for strength in STRENGTHS:
                row={'source':name,'placement':placement,'strength':strength,'success':False}
                try:
                    if failure:raise ValueError('source preparation: '+failure)
                    ba=big_alpha if placement=='original' else np.fliplr(big_alpha).copy();sa=small_alpha if placement=='original' else np.fliplr(small_alpha).copy();combined=np.maximum(ba,sa)
                    if np.any((combined>.2)&~core):raise ValueError('intervention outside core')
                    edited=synthesize(raw['C'],combined,strength); edit_aligned,state=previous.align(src,edited,core);row['alignments']={**alignment,'E':state}
                    if not state['success']:raise ValueError('edited alignment')
                    wb=warp_alpha(ba,state['matrix']);ws=warp_alpha(sa,state['matrix']);wa=np.maximum(wb,ws);b=(wb>=.8)&core;s=(ws>=.8)&core;valid=core&~((wa>.2)&(wa<.8))
                    positive=sim.base.luma(edit_aligned)-sim.base.luma(aligned['A']);pred,unknown,t=stratify.labels(cal,positive,core,True);t.update(control);met=scoring.metrics(pred,unknown,b,s,valid,core);row.update(success=True,thresholds=t,metrics=met,core_pixels_before={'big':int((ba>=.8).sum()),'small':int((sa>=.8).sum())});row['gates']=gates(row);row['passed']=all(row['gates'].values())
                    case=output/f'{name}-{placement}-{strength:.2f}';case.mkdir()
                    for key,img in [('intervention',edited),('intervention-aligned',edit_aligned),('confirmed',(pred*255).astype('uint8')),('unknown',(unknown*255).astype('uint8')),('reference-core',((b|s)*255).astype('uint8'))]:Image.fromarray(img).save(case/(key+'.png'))
                except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                rows.append(row)
        print(name,'done',flush=True)
    assert reg.read_bytes()==before
    result={'protocol':'round62-protocol.md','source_sha256':provenance,'cases':rows,'passed':sum(bool(x.get('passed')) for x in rows),'total':len(rows),'registry_sha256':hashlib.sha256(before).hexdigest(),'used_for_training':False,'limitations':['same two previously observed sources','programmed RGB intervention not true generated lesion','positive and negative share C image','control drift not actual lesion editing drift','no real patient performance']}
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'total':len(rows),'failed_processing':sum(not r['success'] for r in rows)}),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--project',type=Path,required=True);a=p.parse_args();run(a.inputs,a.output,a.project)
if __name__=='__main__':main()
