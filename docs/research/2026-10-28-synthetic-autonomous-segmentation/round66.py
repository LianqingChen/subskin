"""Evaluate frozen synthetic models on previously generated controls and known edits."""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
from PIL import Image
import torch
import round61 as prev
import round63 as reference

MODELS=(('mixed',19,52),('mixed',43,52),('safe',19,55),('safe',43,55))

def score(pred,core,truth=None,big=None,small=None):
    pred=pred.astype(bool);p=pred&core;out={'inside_pred_pixels':int(p.sum()),'outside_pred_pixels':int((pred&~core).sum()),'inside_pred_pct':float(100*p.sum()/core.sum())}
    if truth is not None:
        truth=truth&core;n=int(truth.sum());bn=int((big&core).sum());sn=int((small&core).sum())
        if min(n,bn,sn)==0:raise ValueError('empty reference')
        count=int(p.sum());out.update(dice=float(2*(p&truth).sum()/(count+n)),relative_area_error=float(abs(count-n)/n),big_recall=float((p&big).sum()/bn),small_recall=float((p&small).sum()/sn),truth_pixels=n)
    return out

def run(project,research,output):
    sys.path.insert(0,str(project));from ml.rgb_segmentation.evaluate import predict
    torch.set_num_threads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('output not empty')
    output.mkdir(parents=True,exist_ok=True);casesdir=research/'round65-artifacts/completed';inputs=research/'round65-artifacts/inputs';old=json.loads((casesdir/'results.json').read_text());provenance=json.loads((inputs.parent/'input-provenance.json').read_text());hashes={}
    for n,meta in provenance['files'].items():
        path=inputs/(n+'.png');h=prev.sha(path);assert h==meta['sha256'];hashes[n]=h
    rows=[];models={}
    for kind,seed,roundno in MODELS:
        label=f'{kind}-{seed}';folder=research/f'round{roundno}-artifacts'/label;weights=folder/'baseline.pt';summary=json.loads((folder/'summary.json').read_text());weight_hash=prev.sha(weights);assert weight_hash==summary['model_sha256'];model=torch.jit.load(str(weights),map_location='cpu').eval();models[label]={'sha256':weight_hash,'prior_status':summary['status']}
        for source in ('arm','hand'):
            src,_=prev.read_letterbox(inputs/f'source-{source}.png');core=prev.skin_core(src);c,_=prev.read_letterbox(inputs/f'{source}-C.png');aligned,state=prev.align(src,c,core)
            if not state['success']:raise ValueError('control alignment')
            row={'model':label,'source':source,'kind':'negative','success':False}
            try:
                pred=predict(model,aligned)==2;row.update(success=True,metrics=score(pred,core))
            except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
            rows.append(row)
            for oldcase in [x for x in old['cases'] if x['source']==source and x['method']=='single']:
                row={'model':label,'source':source,'kind':'positive','placement':oldcase['placement'],'strength':oldcase['strength'],'success':False}
                try:
                    if not oldcase['success']:raise ValueError('round65 input failure')
                    folder=casesdir/f"{source}-{oldcase['placement']}-{oldcase['strength']:.2f}";img=np.asarray(Image.open(folder/'intervention-aligned.png').convert('RGB'));truth=np.asarray(Image.open(folder/'reference-alpha05.png').convert('L'))>0;big,small,_=reference.reference(core,oldcase['placement'],oldcase['alignments']['E']['matrix']);pred=predict(model,img)==2
                    row.update(success=True,metrics=score(pred,core,truth,big,small))
                    target=output/label;target.mkdir(exist_ok=True);Image.fromarray((pred*255).astype('uint8')).save(target/f"{source}-{oldcase['placement']}-{oldcase['strength']:.2f}.png")
                except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                rows.append(row)
        print(label,'done',flush=True)
    assert before==reg.read_bytes()
    out={'protocol':'round66-protocol.md','models':models,'input_sha256':hashes,'round65_results_sha256':prev.sha(casesdir/'results.json'),'rows':rows,'registry_sha256':hashlib.sha256(before).hexdigest(),'training':False,'limits':['two previously observed sources','C controls shared by positives','program reference not clinical','512 resized canvas differs from diary inputs']};(output/'results.json').write_text(json.dumps(out,indent=2)+'\n');print('rows',len(rows),'errors',sum(not x['success'] for x in rows),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','research','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.research,a.output)
if __name__=='__main__':main()
