"""Second synthetic-only exploratory experiment; no real photos or annotations."""
import argparse
import importlib.util
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch

spec = importlib.util.spec_from_file_location('pilot', Path(__file__).with_name('experiment.py'))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
N = 64
Y, X = np.mgrid[:N, :N].astype(np.float32)


def make_test(seed):
    rng = np.random.default_rng(seed)
    palette = np.array([[.30,.17,.13],[.45,.27,.20],[.60,.40,.31],[.76,.55,.45],[.88,.72,.63]], np.float32)
    i = int(rng.integers(4))
    mix = rng.uniform(0, 1)
    base = palette[i] * (1 - mix) + palette[i+1] * mix
    # Sinusoids, not the first generator's interpolated random fields.
    tex = np.zeros((N, N), np.float32)
    for _ in range(6):
        angle = rng.uniform(0, 2*np.pi)
        frequency = rng.uniform(.07, .7)
        phase = rng.uniform(0, 2*np.pi)
        tex += rng.uniform(.002, .012) * np.sin(frequency * (X*np.cos(angle) + Y*np.sin(angle)) + phase)
    texture = tex + rng.normal(0, .006, (N,N)).astype(np.float32)
    illumination = 1 + rng.uniform(-.20,.20)*(X/N-.5) + rng.uniform(-.20,.20)*(Y/N-.5)
    image = np.clip(base[None,None,:] * illumination[...,None] + texture[...,None], 0, 1)
    negative = bool(rng.random() < .30)
    small = False
    alpha = np.zeros((N,N), np.float32)
    if not negative:
        small = bool(rng.random() < .35)
        radius = rng.uniform(3, 5.5) if small else rng.uniform(8, 19)
        cx, cy = rng.uniform(18, 46, 2)
        # Irregular polygon, blurred edge; target is alpha >= .5.
        count = 17
        angles = np.linspace(0, 2*np.pi, count, endpoint=False)
        radii = radius * rng.uniform(.65, 1.35, count)
        pts = np.stack([cx + radii*np.cos(angles), cy + radii*np.sin(angles)],1).astype(np.int32)
        shape = np.zeros((N,N), np.uint8)
        cv2.fillPoly(shape,[pts],1)
        alpha = cv2.GaussianBlur(shape.astype(np.float32),(0,0),rng.uniform(.6,1.8))
        # Partial pigment reduction and slight spatial heterogeneity.
        strength = rng.uniform(.07,.25) * (1 + .14*np.sin(.2*X + rng.uniform(0,6.28)))
        image = image + alpha[...,None] * strength[...,None] * (1-image)
    # Elliptical smooth highlights and shadow independent of lesion labels.
    for _ in range(int(rng.integers(2,5))):
        cx,cy = rng.uniform(0,N,2)
        sx,sy = rng.uniform(3,17,2)
        blob = np.exp(-((X-cx)**2/(2*sx*sx)+(Y-cy)**2/(2*sy*sy)))
        image += blob[...,None]*rng.uniform(-.12,.16)
    image=np.clip(image,0,1).astype(np.float32)
    target=(alpha>=.5).astype(np.float32)
    return image,target,{'negative':negative,'small':small,'seed':seed}


def make_batch(start, count):
    rows=[make_test(i) for i in range(start,start+count)]
    x=torch.from_numpy(np.stack([a.transpose(2,0,1) for a,_,_ in rows]))
    y=torch.from_numpy(np.stack([b for _,b,_ in rows])[:,None])
    return x,y,[c for _,_,c in rows]


def perturb(x):
    # One deterministic, identical camera perturbation for each method.
    gains=torch.tensor([1.12,.94,.83]).view(1,3,1,1)
    return (x*gains+.025).clamp(0,1)


def threshold(p,y,meta):
    candidates=[]
    for value in np.arange(.10,.901,.05):
        metrics=pilot.evaluate(p,y,meta,float(value))
        if metrics['negative_false_positive_area_pct'] <= 2:
            candidates.append((metrics['positive_dice'],float(value)))
    if not candidates:
        return .9, False
    # For equal validation Dice choose higher threshold.
    return max(candidates)[1],True


def evaluate(p,p2,y,meta,t):
    output=pilot.evaluate(p,y,meta,t)
    output['perturbed']=pilot.evaluate(p2,y,meta,t)
    mask=p>=t
    mask2=p2>=t
    output['mean_abs_area_change_pp']=float(np.mean(np.abs(mask.mean(axis=(1,2))-mask2.mean(axis=(1,2))))*100)
    return output


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--preview',required=True);args=ap.parse_args()
    torch.set_num_threads(2); started=time.time()
    val_x,val_y,val_meta=pilot.batch(200000,128,'mixed')
    test_x,test_y,test_meta=make_batch(400000,128)
    assert sum(x['negative'] for x in test_meta)>=20
    assert sum(x['small'] for x in test_meta)>=20
    assert all(not test_y[j].any().item() for j,m in enumerate(test_meta) if m['negative'])
    different=perturb(test_x)
    from PIL import Image,ImageDraw
    im=Image.new('RGB',(768,384),'white');draw=ImageDraw.Draw(im)
    for i in range(8):
        rgb=(test_x[i].numpy().transpose(1,2,0)*255).astype(np.uint8)
        xx,yy=(i%4)*192,(i//4)*192
        im.paste(Image.fromarray(rgb).resize((160,160)),(xx,yy))
        draw.text((xx,yy+161),str(test_meta[i]['seed'])+(' negative' if test_meta[i]['negative'] else ' positive'),fill='black')
    im.save(args.preview)
    spec2=importlib.util.spec_from_file_location('draft',Path(__file__).with_name('baseline_lesion_draft.py'));rule=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(rule)
    def rule_pred(x):
        result=[]
        for image in x.numpy():
            rgb=(image.transpose(1,2,0)*255).astype(np.uint8)
            skin=np.ones((N,N),bool)
            result.append(rule.draft_lesion(rgb,skin,np.zeros_like(skin))['lesion'].astype('float32'))
        return np.stack(result)
    out={'description':'independent procedural rendering stress test, not real clinical images','train_seed_range':[10000,10511],'validation_seed_range':[200000,200127],'test_seed_range':[400000,400127],'epochs':15,'n_test':len(test_meta),'n_negative':sum(m['negative'] for m in test_meta),'n_small':sum(m['small'] for m in test_meta),'limitations':['binary segmentation with oracle full-image skin','no pretrained model','synthetic inputs only','same preset skin palette as training'],'models':{}}
    out['models']['production_lesion_draft_oracle_skin']={'threshold':.5,'test':evaluate(rule_pred(test_x),rule_pred(different),test_y,test_meta,.5)}
    for aug,cons,name in [(False,False,'diverse'),(True,False,'augmented'),(True,True,'consistency')]:
        out['models'][name]=[]
        for seed in (0,1):
            net=pilot.fit('mixed',aug,cons,seed,15,512)
            val_p=pilot.prob(net,val_x)
            t,feasible=threshold(val_p,val_y,val_meta)
            p=pilot.prob(net,test_x); p2=pilot.prob(net,different)
            out['models'][name].append({'seed':seed,'threshold':round(t,3),'validation_constraint_met':feasible,'validation':pilot.evaluate(val_p,val_y,val_meta,t),'test':evaluate(p,p2,test_y,test_meta,t)})
            print(name,seed,'done',flush=True)
    out['elapsed_seconds']=round(time.time()-started,2)
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
