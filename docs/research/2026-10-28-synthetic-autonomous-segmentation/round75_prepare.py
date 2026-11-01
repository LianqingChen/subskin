"""Add known synthetic paired edits to previously generated fictional skin."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
import round74_prepare as base
import round69_prepare as synth
import round75_shapes as shapes

NAMES=('light-arm','dark-arm','light-hand','dark-hand')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(project,inputs,negative_manifest,output):
    reg=project/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];orig=json.loads(negative_manifest.read_text());assert orig['eligible']
    if output.exists() and any(output.iterdir()):raise ValueError('nonempty output')
    output.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(7505);items=[];errors=[]
    for name in NAMES:
        try:
            src=inputs/f'{name}.png';expected=orig['sources'][name];assert sha(src)==expected['source_sha256'];canvas,core,info=base.core_from_image(src);oldcore=np.asarray(Image.open(negative_manifest.parent/expected['files']['core512']['file']))>0
            if not np.array_equal(core,oldcore):raise ValueError('core mismatch')
            for i,strength in enumerate((.04,.06,.08,.12,.20,.28)):
                try:
                    (big,small),loc=shapes.shape_fields(core,rng);edited,pos,neg=synth.build_pair(canvas,core,big,small,strength);rgbpos=synth.resized(edited,Image.Resampling.BILINEAR);rgbneg=synth.resized(canvas,Image.Resampling.BILINEAR);ypos=synth.resized(pos,Image.Resampling.NEAREST);yneg=synth.resized(neg,Image.Resampling.NEAREST);counts=[int((synth.resized(x,Image.Resampling.NEAREST)>=.8).sum()) for x in (big,small)]
                    if min(counts)<1 or not ((ypos==2)&(yneg==1)).any():raise ValueError('missing resized core')
                    key=f'{name}-{i:02d}';files={}
                    for label,arr in [('positive',rgbpos),('negative',rgbneg),('positive-mask',ypos),('negative-mask',yneg)]:
                        p=output/f'{key}-{label}.png';Image.fromarray(arr).save(p);files[label]={'name':p.name,'sha256':sha(p)}
                    items.append({'id':key,'source':name,'strength':strength,'location':loc,'core_pixels_128':counts,'files':files})
                except Exception as exc:errors.append({'source':name,'index':i,'error':f'{type(exc).__name__}: {exc}'})
        except Exception as exc:errors.append({'source':name,'error':f'{type(exc).__name__}: {exc}'})
    assert before==reg.read_bytes();doc={'protocol':'round75-protocol.md','source_manifest_sha256':sha(negative_manifest),'seed':7505,'pairs':items,'errors':errors,'eligible':len(items)==24 and not errors,'registry_sha256':hashlib.sha256(before).hexdigest()};(output/'manifest.json').write_text(json.dumps(doc,indent=2)+'\n');print(json.dumps({'pairs':len(items),'errors':errors,'eligible':doc['eligible']}),flush=True)

def main():
    p=argparse.ArgumentParser()
    for n in ('project','inputs','negative-manifest','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.project,a.inputs,a.negative_manifest,a.output)
if __name__=='__main__':main()
