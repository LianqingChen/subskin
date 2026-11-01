"""Recreate and archive the pre-specified alpha reference regions."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image
import round61 as prev
import round71 as experiment

def run(inputs,completed):
    results=json.loads((completed/'results.json').read_text());rng=np.random.default_rng(7005);records={}
    for name in experiment.NAMES:
        try:z=experiment.prepare_source(name,inputs,rng)
        except Exception:
            if results['sources'][name]['status']!='error':raise
            continue
        expected=results['sources'][name]['locations']
        for i,pos in enumerate(z['positions']):
            if pos['error']!=expected[i]['error'] or pos.get('location')!=expected[i].get('location'):raise ValueError('position differs from evaluation')
            if pos['error']:continue
            big,small=pos['big'],pos['small'];core=z['core'];alpha=np.maximum(big,small);folder=completed/'references';folder.mkdir(exist_ok=True)
            for label,mask in [('full',(alpha>=.5)&core),('big',(big>=.8)&core),('small',(small>=.8)&core)]:
                path=folder/f'{name}-p{i}-{label}.png';Image.fromarray(mask.astype('uint8')*255).save(path);records[path.name]={'sha256':prev.sha(path),'pixels':int(mask.sum())}
    path=completed/'reference-provenance.json';path.write_text(json.dumps(records,indent=2)+'\n');print('reference masks',len(records))

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--completed',type=Path,required=True);a=p.parse_args();run(a.inputs,a.completed)
if __name__=='__main__':main()
