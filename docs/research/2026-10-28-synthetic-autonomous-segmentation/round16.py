"""Spatial illumination and lesion-size synthetic study; no clinical data."""
import argparse,importlib.util,json,time
from pathlib import Path
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r15',HERE/'round15.py');r15=importlib.util.module_from_spec(s);s.loader.exec_module(r15)
r11=r15.r11;r12=r15.r12;r14=r15.r14


def spatial_correct(mapped,ref,core):
    h,w=core.shape;yy,xx=np.mgrid[:h,:w];x=(xx-w/2)/(w/2);y=(yy-h/2)/(h/2)
    basis=np.stack([np.ones_like(x),x,y,x*x,x*y,y*y],axis=-1);X=basis[core][::4];z=((ref-mapped)[core][::4]/255.).astype('float64');keep=np.ones(len(z),bool)
    if len(z)<100:return None,{'success':False,'reason':'too_few_samples'}
    for _ in range(5):
        if keep.mean()<.5:return None,{'success':False,'reason':'insufficient_inliers'}
        coef,_,rank,_=np.linalg.lstsq(X[keep],z[keep],rcond=None)
        if rank<6 or not np.isfinite(coef).all():return None,{'success':False,'reason':'unstable_fit'}
        residual=z-X@coef;med=float(np.median(residual));mad=float(np.median(np.abs(residual-med)));keep=np.abs(residual-med)<=max(4*1.4826*mad,2/255.)
    if keep.mean()<.5:return None,{'success':False,'reason':'insufficient_inliers'}
    correction=(basis@coef)*255
    if not np.isfinite(correction).all() or np.max(np.abs(correction[core]))>40:return None,{'success':False,'reason':'excessive_correction'}
    return np.clip(mapped+correction,0,255).astype('float32'),{'success':True,'inlier_pct':float(100*keep.mean()),'max_abs_correction':float(np.max(np.abs(correction[core]))),'coefficients':coef.tolist()}


def synth(src,core,seed,size):
    rng=np.random.default_rng(seed);h,w=core.shape
    def center(x1,x2):
        z=np.argwhere(core);z=z[(z[:,1]>=int(w*x1))&(z[:,1]<int(w*x2))];assert len(z)>0
        # Select central vertical position from the available pixels.
        xy=z[np.argsort(np.abs(z[:,1]-int(w*(x1+x2)/2)))[:max(1,len(z)//20)]];return tuple(int(v) for v in xy[np.argsort(xy[:,0])[len(xy)//2]])
    by,bx=center(.15,.40);sy,sx=center(.68,.83);bigshape=np.zeros((h,w),np.uint8);smallshape=bigshape.copy()
    axes=(18,18) if size=='medium' else (65,25);cv2.ellipse(bigshape,(bx,by),axes,0,0,360,1,-1);cv2.circle(smallshape,(sx,sy),5,1,-1)
    ab=cv2.GaussianBlur(bigshape.astype('float32'),(0,0),1.2)*core;ass=cv2.GaussianBlur(smallshape.astype('float32'),(0,0),.8)*core
    big=(ab>=.8)&core;small=(ass>=.8)&core&~big;assert big.any() and small.any() and not np.any(big&small)
    alpha=np.maximum(ab,ass);ignore=(alpha>.2)&(alpha<.8)&core;base=src.astype('float32');edited=np.clip(base+alpha[...,None]*.28*(255-base),0,255)
    def camera(x):
        noisy=np.clip(x+1+rng.normal(0,2,x.shape),0,255).astype('uint8');M=np.array([[1.,0.,2.],[0.,1.,-1.5]],dtype='float32')
        return cv2.warpAffine(noisy,M,r11.SIZE,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    return camera(base),camera(edited),big,small,ignore


def prepare_l(mapped,ref,core,method):
    if method=='raw':return mapped,{'success':True}
    glob,ginfo=r15.fit_map(mapped,ref,core,1)
    if glob is None:return None,{'success':False,'global':ginfo}
    if method=='global':return glob,{'success':True,'global':ginfo}
    loc,linfo=spatial_correct(glob,ref,core)
    if loc is None:return None,{'success':False,'global':ginfo,'local':linfo}
    return loc,{'success':True,'global':ginfo,'local':linfo}


def automatic_gate(mask,info):
    """Uses algorithm outputs only; never inspect synthetic truth or ignore mask."""
    return bool(info['control_right_fp_pct']<=.5 and np.any(mask))

def case(path,seed,size,condition):
    src,_=r11.read(path);core=r11.skin_core(src);ctrl,edit,big,small,ignore=synth(src,core,seed,size);ctrl=r15.degrade(ctrl,condition);edit=r15.degrade(edit,condition)
    ca,ci=r14.feature_align(src,ctrl,core,seed);ea,ei=r14.feature_align(src,edit,core,seed);reg_ok=bool(ci['success'] and ei['success'])
    truth=np.array([[1.,0.,2.],[0.,1.,-1.5]],dtype='float64');geo=r14.r13.p95_delta(ei['matrix'],truth,core) if ei['success'] else None
    row={'source':Path(path).name,'seed':seed,'size':size,'condition':condition,'big_pct_core':float(100*big.sum()/core.sum()),'small_pct_core':float(100*small.sum()/core.sum()),'registration_ok':reg_ok,'geometry_p95_px':geo,'methods':{}}
    if not reg_ok:return row
    ref=r11.luma(src);cl=r11.luma(ca);el=r11.luma(ea)
    for method in ('raw','global','spatial'):
        cc,cinfo=prepare_l(cl,ref,core,method);ee,einfo=prepare_l(el,ref,core,method)
        if cc is None or ee is None:row['methods'][method]={'fit_ok':False,'control_fit':cinfo,'edited_fit':einfo};continue
        mask,info=r15.difference(ref,cc,ee,core);sc=r12.score(mask,big,small,core&~ignore)
        gate=automatic_gate(mask,info)
        row['methods'][method]={'fit_ok':True,'auto_gate_pass':gate,'control_fit':cinfo,'edited_fit':einfo,'difference':info,'scores':sc}
    return row


def summary(rows,method):
    good=[r for r in rows if r['registration_ok'] and r['methods'][method]['fit_ok']];passed=[r for r in good if r['methods'][method]['auto_gate_pass']]
    def mean(key):return float(np.mean([r['methods'][method]['scores'][key] or 0 for r in good])) if good else None
    return {'total':len(rows),'fit_ok':len(good),'auto_gate_pass':len(passed),'coverage_pct':100*len(passed)/len(rows),'mean_big_recall_all_fit':mean('big_recall'),'mean_small_recall_all_fit':mean('small_recall'),'mean_precision_all_fit':mean('precision'),'mean_control_fp_pct_all_fit':float(np.mean([r['methods'][method]['difference']['control_right_fp_pct'] for r in good])) if good else None,'passed_low_big_recall':sum(r['methods'][method]['scores']['big_recall']<.5 for r in passed),'passed_low_small_recall':sum(r['methods'][method]['scores']['small_recall']<.5 for r in passed),'passed_bad_geometry':sum(r['geometry_p95_px']>3 for r in passed)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--light',required=True);p.add_argument('--dark',required=True);p.add_argument('--output',required=True);a=p.parse_args();start=time.time();cv2.setNumThreads(2);sources=[Path(a.light),Path(a.dark)];assert r11.checksum(sources[0])!=r11.checksum(sources[1]);rows=[]
    for source in sources:
        for size in ('medium','large'):
            for cond in ('identity','gamma_2','gradient'):
                for seed in (24000,24001):rows.append(case(source,seed,size,cond))
                print(source.name,size,cond,'done',flush=True)
    out={'protocol':'round16-protocol.md','source_hashes':[r11.checksum(p) for p in sources],'cases':rows,'by_size_condition':{},'overall':{},'limitations':['two AI-generated source backgrounds','programmatic bright lesions','source and target are paired with known synthetic warp','not clinical labels','boundary ignored','percentages are relative to skin core'],'elapsed_seconds':round(time.time()-start,2)}
    for m in ('raw','global','spatial'):out['overall'][m]=summary(rows,m)
    for size in ('medium','large'):
        for cond in ('identity','gamma_2','gradient'):
            subset=[r for r in rows if r['size']==size and r['condition']==cond];out['by_size_condition'][size+'/'+cond]={m:summary(subset,m) for m in ('raw','global','spatial')}
    Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'overall':out['overall'],'by_size_condition':out['by_size_condition'],'elapsed_seconds':out['elapsed_seconds']},indent=2),flush=True)
if __name__=='__main__':main()
