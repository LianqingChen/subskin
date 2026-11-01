"""Paired whole image and tiled inference for frozen research models."""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
from PIL import Image
import torch
import round61 as prev
import round63 as refs
import round66 as prior


def tiled_predict(model, rgb):
    if rgb.shape!=(512,512,3):raise ValueError('expected 512 RGB')
    tensor=torch.from_numpy(rgb.copy()).permute(2,0,1).float()/255
    coords=[(y,x) for y in range(0,385,64) for x in range(0,385,64)]
    probs=torch.zeros((5,512,512));counts=torch.zeros((512,512))
    with torch.inference_mode():
        for i in range(0,len(coords),8):
            part=coords[i:i+8];batch=torch.stack([tensor[:,y:y+128,x:x+128] for y,x in part]);logits=model(batch)
            if logits.shape!=(len(part),5,128,128) or not torch.isfinite(logits).all():raise ValueError('invalid tile output')
            values=torch.softmax(logits,dim=1)
            for j,(y,x) in enumerate(part):probs[:,y:y+128,x:x+128]+=values[j];counts[y:y+128,x:x+128]+=1
    if not torch.all(counts>0):raise ValueError('uncovered pixels')
    return (probs/counts.unsqueeze(0)).argmax(0).numpy().astype('uint8')

def run(project,research,output):
    sys.path.insert(0,str(project));from ml.rgb_segmentation.evaluate import predict
    torch.set_num_threads(2);reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if output.exists() and any(output.iterdir()):raise ValueError('output not empty')
    output.mkdir(parents=True,exist_ok=True);casesdir=research/'round65-artifacts/completed';inputs=research/'round65-artifacts/inputs';old65=json.loads((casesdir/'results.json').read_text());old66=json.loads((research/'round66-artifacts/completed/results.json').read_text());mismatches=[];rows=[]
    for name,sha in old66['input_sha256'].items():assert prev.sha(inputs/(name+'.png'))==sha
    assert prev.sha(casesdir/'results.json')==old66['round65_results_sha256']
    for kind,seed,num in prior.MODELS:
        label=f'{kind}-{seed}';weights=research/f'round{num}-artifacts'/label/'baseline.pt';assert prev.sha(weights)==old66['models'][label]['sha256'];model=torch.jit.load(str(weights),map_location='cpu').eval()
        for source in ('arm','hand'):
            src,_=prev.read_letterbox(inputs/f'source-{source}.png');core=prev.skin_core(src);c,_=prev.read_letterbox(inputs/f'{source}-C.png');negative,state=prev.align(src,c,core)
            if not state['success']:raise ValueError('negative alignment')
            cases=[{'kind':'negative','img':negative}]
            for old in [x for x in old65['cases'] if x['source']==source and x['method']=='single']:
                if not old['success']:raise ValueError('round65 case failure')
                folder=casesdir/f"{source}-{old['placement']}-{old['strength']:.2f}";img=np.asarray(Image.open(folder/'intervention-aligned.png').convert('RGB'));truth=np.asarray(Image.open(folder/'reference-alpha05.png').convert('L'))>0;big,small,_=refs.reference(core,old['placement'],old['alignments']['E']['matrix']);cases.append({'kind':'positive','placement':old['placement'],'strength':old['strength'],'img':img,'truth':truth,'big':big,'small':small})
            for case in cases:
                match=[x for x in old66['rows'] if x['model']==label and x['source']==source and x['kind']==case['kind'] and (case['kind']=='negative' or (x['placement']==case['placement'] and x['strength']==case['strength']))];assert len(match)==1
                for method in ('whole','tiled'):
                    row={'model':label,'source':source,'kind':case['kind'],'method':method,'success':False}
                    if case['kind']=='positive':row.update(placement=case['placement'],strength=case['strength'])
                    try:
                        pred=(predict(model,case['img']) if method=='whole' else tiled_predict(model,case['img']))==2
                        met=prior.score(pred,core,case.get('truth'),case.get('big'),case.get('small'));row.update(success=True,metrics=met)
                        if method=='whole' and (not match[0]['success'] or met!=match[0]['metrics']):mismatches.append({k:row[k] for k in ('model','source','kind','method')})
                        if method=='tiled':
                            folder=output/label;folder.mkdir(exist_ok=True);stem=source+'-negative' if case['kind']=='negative' else f"{source}-{case['placement']}-{case['strength']:.2f}";Image.fromarray((pred*255).astype('uint8')).save(folder/(stem+'.png'))
                    except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}';mismatches.append({'error':row})
                    rows.append(row)
        print(label,'completed',flush=True)
    assert before==reg.read_bytes();result={'protocol':'round67-protocol.md','baseline_reproduced':not mismatches,'mismatches':mismatches,'prior_results_sha256':prev.sha(research/'round66-artifacts/completed/results.json'),'rows':rows,'registry_sha256':hashlib.sha256(before).hexdigest(),'trained':False,'limitations':['two observed sources','model groupnorm changes with tile context','tile size not equal resized full training image','not a production or clinical test']};(output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'rows':len(rows),'baseline_reproduced':not mismatches,'errors':sum(not x['success'] for x in rows)}),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','research','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.research,a.output)
if __name__=='__main__':main()
