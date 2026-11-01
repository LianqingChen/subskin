"""Robust luminance mappings for paired synthetic edits; not medical labels."""
import argparse,importlib.util,json,time
from pathlib import Path
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r14',HERE/'round14.py');r14=importlib.util.module_from_spec(sp);sp.loader.exec_module(r14)
r11=r14.r11;r12=r14.r12


def fit_map(moving_l,reference_l,core,degree):
    # Fixed every-fourth sampling, independent of label or target region.
    x=(moving_l[core].ravel()[::4]/255.).astype('float64');y=(reference_l[core].ravel()[::4]/255.).astype('float64')
    if len(x)<100 or float(np.ptp(x))<.025:return None,{'success':False,'reason':'insufficient_dynamic_range'}
    X=np.stack([x**j for j in range(degree+1)],axis=1);keep=np.ones(len(x),bool)
    for _ in range(5):
        if keep.mean()<.5:return None,{'success':False,'reason':'insufficient_inliers'}
        coef,_,rank,_=np.linalg.lstsq(X[keep],y[keep],rcond=None)
        if rank<degree+1 or not np.isfinite(coef).all():return None,{'success':False,'reason':'unstable_fit'}
        residual=y-X@coef;median=float(np.median(residual));mad=float(np.median(np.abs(residual-median)));limit=max(4.*1.4826*mad,2./255.)
        keep=np.abs(residual-median)<=limit
    if keep.mean()<.5:return None,{'success':False,'reason':'insufficient_inliers'}
    lo,hi=float(x[keep].min()),float(x[keep].max());grid=np.linspace(lo,hi,256);deriv=sum(j*coef[j]*grid**(j-1) for j in range(1,len(coef)))
    if not np.isfinite(deriv).all() or (deriv<0).any():return None,{'success':False,'reason':'non_monotone'}
    full=np.clip(moving_l/255.,lo,hi);mapped=sum(coef[j]*full**j for j in range(len(coef)))*255.
    return np.clip(mapped,0,255).astype('float32'),{'success':True,'degree':degree,'inlier_pct':float(100*keep.mean()),'lower_l':lo*255,'upper_l':hi*255,'clamped_pct_core':float(100*np.mean((moving_l[core]/255.<lo)|(moving_l[core]/255.>hi))),'coefficients':coef.tolist()}


def degrade(im,mode):
    if mode=='identity':return im
    x=im.astype('float32')/255.
    if mode=='gamma_1_4':x=x**1.4
    elif mode=='gamma_2':x=x**2.
    elif mode=='gradient':x=x*np.linspace(.55,.95,x.shape[1],dtype='float32')[None,:,None]
    else:raise ValueError(mode)
    return np.clip(x*255,0,255).astype('uint8')


def difference(ref,ctrl,edit,core):
    width=core.shape[1];left=core.copy();left[:,width//2:]=False;right=core.copy();right[:,:width//2]=False
    dc=ctrl-ref;de=edit-ref;threshold=float(max(3.,np.quantile(dc[left],.999)))
    return (de>threshold)&core,{'threshold_l_encoded':threshold,'control_right_fp_pct':float(100*np.mean(dc[right]>threshold))}


def make(path,seed,condition):
    src,_=r11.read(path);core=r11.skin_core(src);control,edited,big,small,ignore=r12.synth(src,core,seed)
    control=degrade(control,condition);edited=degrade(edited,condition)
    ca,ci=r14.feature_align(src,control,core,seed);ea,ei=r14.feature_align(src,edited,core,seed);accepted=bool(ci['success'] and ei['success'])
    truth=np.array([[1,0,2],[0,1,-1.5]],dtype='float64');geo=r14.r13.p95_delta(ei['matrix'],truth,core) if ei['success'] else None
    out={'source':Path(path).name,'seed':seed,'condition':condition,'registration_accepted':accepted,'edited_geometry_p95_px':geo,'methods':{}}
    if not accepted:
        out['registration_failure']={'control':ci,'edited':ei};return out
    ref=r11.luma(src);cl=r11.luma(ca);el=r11.luma(ea)
    for name,degree in [('raw',None),('linear',1),('cubic',3)]:
        if degree is None:cc,ee=cl,el;cinfo=einfo={'success':True}
        else:cc,cinfo=fit_map(cl,ref,core,degree);ee,einfo=fit_map(el,ref,core,degree)
        if cc is None or ee is None:
            out['methods'][name]={'accepted':False,'control_fit':cinfo,'edited_fit':einfo};continue
        mask,info=difference(ref,cc,ee,core);out['methods'][name]={'accepted':True,'control_fit':cinfo,'edited_fit':einfo,'difference':info,'scores':r12.score(mask,big,small,core&~ignore)}
    return out


def summarize(rows,method):
    valid=[r['methods'][method] for r in rows if r['registration_accepted'] and r['methods'][method]['accepted']];n=len(rows)
    return {'total':n,'accepted':len(valid),'coverage_pct':100*len(valid)/n,'mean_small_recall':float(np.mean([q['scores']['small_recall'] for q in valid])) if valid else None,'small_recall_below_half_count':sum(q['scores']['small_recall']<.5 for q in valid),'mean_big_recall':float(np.mean([q['scores']['big_recall'] for q in valid])) if valid else None,'mean_precision':float(np.mean([q['scores']['precision'] if q['scores']['precision'] is not None else 0. for q in valid])) if valid else None,'mean_control_fp_pct':float(np.mean([q['difference']['control_right_fp_pct'] for q in valid])) if valid else None,'accepted_geometry_errors':sum(r['edited_geometry_p95_px']>3 for r in rows if r['registration_accepted'] and r['methods'][method]['accepted'])}


def main():
    p=argparse.ArgumentParser();p.add_argument('--light',required=True);p.add_argument('--dark',required=True);p.add_argument('--output',required=True);a=p.parse_args();cv2.setNumThreads(2);t=time.time();sources=[Path(a.light),Path(a.dark)];assert r11.checksum(sources[0])!=r11.checksum(sources[1]);rows=[]
    for path in sources:
        for mode in ('identity','gamma_1_4','gamma_2','gradient'):
            for seed in (23000,23001,23002):rows.append(make(path,seed,mode))
            print(path.name,mode,'done',flush=True)
    out={'protocol':'round15-protocol.md','source_hashes':[r11.checksum(p) for p in sources],'cases':rows,'overall':{},'by_condition':{},'by_source':{},'limitations':['known programmatically imposed edits, not true vitiligo','only two AI-generated base images','registration and color mapping use shared source','bright synthetic lesions only','uncertain edge pixels ignored','OpenCV encoded-L scale'],'elapsed_seconds':round(time.time()-t,2)}
    for name in ('raw','linear','cubic'):out['overall'][name]=summarize(rows,name)
    for mode in ('identity','gamma_1_4','gamma_2','gradient'):
        subset=[r for r in rows if r['condition']==mode];out['by_condition'][mode]={name:summarize(subset,name) for name in ('raw','linear','cubic')}
    for path in sources:
        subset=[r for r in rows if r['source']==path.name];out['by_source'][path.name]={name:summarize(subset,name) for name in ('raw','linear','cubic')}
    Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'overall':out['overall'],'by_condition':out['by_condition'],'elapsed_seconds':out['elapsed_seconds']},indent=2),flush=True)
if __name__=='__main__':main()
