"""Image-level disagreement and coverage, synthetic data only."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
import torch
from PIL import Image
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r5',HERE/'round5.py');r5=importlib.util.module_from_spec(spec);spec.loader.exec_module(r5)
r3=r5.r3;r4=r5.r4


def make_test(base):
    out={}
    for i,kind in enumerate(('standard','weak','glare')):
        out[kind]=r5.batch_rows([r5.independent_case(base,930000+1000*i+j,kind) for j in range(32)])
    return out


def group_metrics(pred,truth,accepted,negative):
    n=len(pred);idx=np.flatnonzero(accepted);areas=pred.mean(axis=(1,2))*100
    ans={'n_total':n,'n_accepted':len(idx),'coverage_pct':float(100*len(idx)/n),'rejected_pct':float(100*(n-len(idx))/n)}
    if negative:
        fp=(areas>1)
        ans['accepted_fp_image_gt_1pct']=None if len(idx)==0 else float(100*fp[idx].mean())
        ans['accepted_mean_fp_area_pct']=None if len(idx)==0 else float(areas[idx].mean())
        ans['all_cases_auto_fp_gt_1pct']=float(100*np.mean(fp&accepted))
    else:
        i=(pred&truth).sum(axis=(1,2));denom=pred.sum(axis=(1,2))+truth.sum(axis=(1,2));gold=truth.sum(axis=(1,2))
        ans['accepted_dice']=None if len(idx)==0 else float(np.mean(2*i[idx]/(denom[idx]+1e-9)))
        ans['accepted_pixel_recall']=None if len(idx)==0 else float(i[idx].sum()/gold[idx].sum())
        ans['all_cases_effective_pixel_recall']=float(i[accepted].sum()/gold.sum())
        ans['all_cases_effective_detected_pct']=float(100*np.mean((i>0)&accepted))
    return ans


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--images',required=True);ap.add_argument('--heads',required=True);ap.add_argument('--sam-package',required=True);ap.add_argument('--sam-weights',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    start=time.time();torch.set_num_threads(4);im=Path(a.images);heads=Path(a.heads)
    paths=[im/x for x in ('train-medium.png','val-light.png','test4-light.png','test4-dark.png','test5-medium.png','test6-medium.png')]
    hashes=[r3.digest(x) for x in paths];assert len(set(hashes))==len(hashes)
    cal=[]
    for j,path in enumerate(paths[2:4]):
        for kind,(x,y,meta) in r4.cases(path,j).items():cal.append((f'{path.stem}/{kind}',x,y,meta))
    with Image.open(paths[5]) as src:base=np.asarray(src.convert('RGB'))
    tests=make_test(base)
    for kind,(x,y,meta) in tests.items():assert all(bool(y[i].any()) != item['negative'] for i,item in enumerate(meta))
    xs=torch.cat([v[1] for v in cal]+[v[0] for v in tests.values()]); ncal=sum(len(v[1]) for v in cal)
    sam_hash=r3.digest(a.sam_weights);results5=json.loads((HERE/'round5-results.json').read_text())
    features=r3.encode(r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights)),xs)
    probabilities=[];source=[]
    for group in ('original','hard_examples'):
        for seed in (0,1):
            path=heads/f'{group}_seed{seed}.pt';sha=hashlib.sha256(path.read_bytes()).hexdigest();row=results5['groups'][group][seed]
            assert sha==row['checkpoint_sha256'] and row['seed']==seed
            ck=torch.load(path,map_location='cpu',weights_only=True);assert ck['sam_sha256']==sam_hash and round(ck['threshold'],3)==.9
            model=r3.Head().eval();model.load_state_dict(ck['model_state_dict']);probabilities.append(r3.predict(model,xs,features));source.append({'group':group,'seed':seed,'sha256':sha})
    p=np.stack(probabilities);mean=p.mean(axis=0);pred=mean>=.9
    disagreement=np.quantile(np.abs(p[:2].mean(axis=0)-p[2:].mean(axis=0)),.95,axis=(1,2))
    cal_unc=disagreement[:ncal];test_unc=disagreement[ncal:]
    assert len(cal_unc)==192 and len(test_unc)==96
    thresholds={str(q):float(np.quantile(cal_unc,q)) for q in (.2,.5,.8)}
    rules={'all':None,**thresholds};result={'protocol':'round6-protocol.md','image_sha256':hashes,'heads':source,'sam_sha256':sam_hash,'calibration_count':ncal,'test_count':len(test_unc),'calibration_thresholds':thresholds,'rules':{},'limitations':['192 correlated synthetic calibration crops from two bases','96 correlated synthetic test crops from one base','0.9 model threshold failed prior validation gate','image-level disagreement not calibrated risk','no real patient images','binary segmentation assumes skin'],'elapsed_seconds':0}
    for label,t in rules.items():
        accepted=np.ones(len(test_unc),bool) if t is None else test_unc<=t
        entry={'overall_coverage_pct':float(100*accepted.mean()),'groups':{}}
        for j,(kind,(x,y,meta)) in enumerate(tests.items()):
            sl=slice(j*32,(j+1)*32);truth=y.numpy()[:,0].astype(bool)
            entry['groups'][kind]=group_metrics(pred[ncal:][sl],truth,accepted[sl],kind=='glare')
        result['rules'][label]=entry
    result['elapsed_seconds']=round(time.time()-start,2)
    Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
