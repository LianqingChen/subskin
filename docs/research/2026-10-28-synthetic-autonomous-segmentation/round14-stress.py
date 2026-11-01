"""Post-hoc stress protocol for controlled image degradation."""
import argparse,importlib.util,json,time
from pathlib import Path
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r14',HERE/'round14.py');r14=importlib.util.module_from_spec(s);s.loader.exec_module(r14)
r11=r14.r11;r12=r14.r12


def degrade(im,kind):
    if kind=='blur_1_5':return cv2.GaussianBlur(im,(0,0),1.5)
    if kind=='blur_3':return cv2.GaussianBlur(im,(0,0),3.)
    if kind=='jpeg_15':
        ok,buf=cv2.imencode('.jpg',cv2.cvtColor(im,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,15]);assert ok
        return cv2.cvtColor(cv2.imdecode(buf,cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
    if kind=='gamma_2':return np.clip((im.astype('float32')/255.)**2*255,0,255).astype('uint8')
    raise ValueError(kind)


def make(path,seed,kind):
    src,_=r11.read(path);core=r11.skin_core(src);c,e,big,small,ignore=r12.synth(src,core,seed);c=degrade(c,kind);e=degrade(e,kind)
    truth=np.array([[1.,0.,2.],[0.,1.,-1.5]],dtype='float32');methods={}
    for method in ('ecc_affine','sift_ransac'):
        if method=='ecc_affine':ca,ci=r11.align(src,c,core);ea,ei=r11.align(src,e,core)
        else:ca,ci=r14.feature_align(src,c,core,seed);ea,ei=r14.feature_align(src,e,core,seed)
        accepted=bool(ci['success'] and ei['success']);geo=r14.r13.p95_delta(ei['matrix'],truth,core) if ei['success'] else None
        row={'accepted':accepted,'control_registration':ci,'edited_registration':ei,'edit_p95_error_px':geo,'geometry_bad_if_accepted':bool(accepted and geo>3.)}
        if accepted:
            scores,pred,_=r11.measure(src,ca,ea,core);row['control_right_fp_pct']=scores['control_right_false_positive_pct'];row['known_lesion_scores']=r12.score(pred,big,small,core&~ignore)
        methods[method]=row
    return {'source':Path(path).name,'seed':seed,'condition':kind,'true_affine':truth.tolist(),'methods':methods}


def main():
    p=argparse.ArgumentParser();p.add_argument('--images',required=True);p.add_argument('--output',required=True);a=p.parse_args();cv2.setNumThreads(2);start=time.time();im=Path(a.images)
    sources=[im/'test8b-arm.png',im/'test10-arm.png'];assert r11.checksum(sources[0])!=r11.checksum(sources[1]);rows=[]
    for path in sources:
        for kind in ('blur_1_5','blur_3','jpeg_15','gamma_2'):
            for seed in (19000,19001,19002):rows.append(make(path,seed,kind))
            print(path.name,kind,'done',flush=True)
    out={'protocol':'round14-stress-protocol.md','status':'post_hoc_followup','source_sha256':[r11.checksum(p) for p in sources],'cases':rows,'overall':{m:r14.summary(rows,m) for m in ('ecc_affine','sift_ransac')},'by_condition':{},'limitations':['two previously used AI-generated sources','synthetic gamma blur jpeg and known translation','not actual diffusion edits or clinical truth'],'elapsed_seconds':round(time.time()-start,2)}
    for kind in ('blur_1_5','blur_3','jpeg_15','gamma_2'):
        x=[z for z in rows if z['condition']==kind];out['by_condition'][kind]={m:r14.summary(x,m) for m in ('ecc_affine','sift_ransac')}
    Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'overall':out['overall'],'by_condition':out['by_condition'],'elapsed_seconds':out['elapsed_seconds']},indent=2),flush=True)
if __name__=='__main__':main()
