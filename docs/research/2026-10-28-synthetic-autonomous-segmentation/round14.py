"""Feature matching versus ECC for controlled synthetic registration only."""
import argparse,importlib.util,json,time
from pathlib import Path
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r13',HERE/'round13.py');r13=importlib.util.module_from_spec(s);s.loader.exec_module(r13)
r12=r13.r12;r11=r12.r11


def feature_align(src,moving,core,seed):
    detector=cv2.SIFT_create(contrastThreshold=.01,edgeThreshold=10)
    a=cv2.cvtColor(src,cv2.COLOR_RGB2GRAY);b=cv2.cvtColor(moving,cv2.COLOR_RGB2GRAY)
    refmask=core.astype('uint8')*255;search=cv2.dilate(refmask,np.ones((31,31),np.uint8))
    kp1,d1=detector.detectAndCompute(a,refmask);kp2,d2=detector.detectAndCompute(b,search)
    result={'success':False,'source_keypoints':len(kp1),'moving_keypoints':len(kp2)}
    if d1 is None or d2 is None or len(d1)<2 or len(d2)<2:
        result['reason']='insufficient_descriptors';return moving,result
    matcher=cv2.BFMatcher(cv2.NORM_L2);forward=matcher.knnMatch(d1,d2,k=2);backward=matcher.knnMatch(d2,d1,k=2)
    def good(pairs):return {p[0].queryIdx:p[0].trainIdx for p in pairs if len(p)==2 and p[0].distance < .75*p[1].distance}
    f=good(forward);rev=good(backward);pairs=[(i,j) for i,j in f.items() if rev.get(j)==i]
    result['mutual_matches']=len(pairs)
    if len(pairs)<8:result['reason']='insufficient_matches';return moving,result
    pts1=np.float32([kp1[i].pt for i,j in pairs]);pts2=np.float32([kp2[j].pt for i,j in pairs]);cv2.setRNGSeed(int(seed))
    matrix,inliers=cv2.estimateAffine2D(pts1,pts2,method=cv2.RANSAC,ransacReprojThreshold=2.,maxIters=2000,confidence=.99,refineIters=10)
    if matrix is None or inliers is None:result['reason']='ransac_failure';return moving,result
    n=int(inliers.sum());fraction=n/len(pairs);det=float(np.linalg.det(matrix[:,:2]));result.update({'inliers':n,'inlier_fraction':fraction,'determinant':det,'matrix':matrix.tolist()})
    if n<6 or fraction<.5 or not np.isfinite(matrix).all() or not .7<=det<=1.3 or abs(matrix[0,2])>r11.SIZE[0]*.2 or abs(matrix[1,2])>r11.SIZE[1]*.2:
        result['reason']='geometry_or_inlier_gate';return moving,result
    out=cv2.warpAffine(moving,matrix,r11.SIZE,flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_CONSTANT)
    result['success']=True;return out,result


def extra_transforms():
    a=[]
    for name,angle,scale in r13.CONDITIONS:a.append((name,cv2.getRotationMatrix2D((256,128),angle,scale).astype('float32')))
    a.append(('shear',np.array([[1.,.02,-2.56],[0.,1.,0.]],dtype='float32')))
    a.append(('anisotropic',np.array([[1.03,0.,-7.68],[0.,.97,3.84]],dtype='float32')))
    return a


def make_case(path,seed,name,extra):
    src,_=r11.read(path);core=r11.skin_core(src);control,edited,big,small,ignore=r12.synth(src,core,seed)
    control=cv2.warpAffine(control,extra,r11.SIZE,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    edited=cv2.warpAffine(edited,extra,r11.SIZE,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    truth=r13.compose(extra,np.array([[1.,0.,2.],[0.,1.,-1.5]],dtype='float32'))
    results={}
    for method in ('ecc_affine','sift_ransac'):
        if method=='ecc_affine': ca,ci=r11.align(src,control,core);ea,ei=r11.align(src,edited,core)
        else: ca,ci=feature_align(src,control,core,seed);ea,ei=feature_align(src,edited,core,seed)
        accepted=bool(ci['success'] and ei['success']);geo=r13.p95_delta(ei['matrix'],truth,core) if ei['success'] else None;cg=r13.p95_delta(ci['matrix'],truth,core) if ci['success'] else None
        row={'accepted':accepted,'control_registration':ci,'edited_registration':ei,'edit_p95_error_px':geo,'control_p95_error_px':cg,'geometry_bad_if_accepted':bool(accepted and geo>3.)}
        if accepted:
            measure,pred,_=r11.measure(src,ca,ea,core);row['control_right_fp_pct']=measure['control_right_false_positive_pct'];row['known_lesion_scores']=r12.score(pred,big,small,core&~ignore)
        results[method]=row
    return {'source':Path(path).name,'seed':seed,'condition':name,'truth':truth.tolist(),'methods':results}


def summary(rows,method):
    accepted=[x['methods'][method] for x in rows if x['methods'][method]['accepted']];n=len(rows);bad=sum(x['geometry_bad_if_accepted'] for x in accepted);low=sum(x['known_lesion_scores']['small_recall']<.5 for x in accepted)
    return {'n':n,'accepted':len(accepted),'coverage_pct':100*len(accepted)/n,'bad_edit_geometry_count':bad,'bad_among_accepted_pct':100*bad/len(accepted) if accepted else None,'accepted_low_small_recall':low,'mean_control_right_fp_pct':float(np.mean([x['control_right_fp_pct'] for x in accepted])) if accepted else None}


def direct_case(srcpath,ctrlpath,editpath):
    src,ss=r11.read(srcpath);ctrl,cs=r11.read(ctrlpath);edit,es=r11.read(editpath);core=r11.skin_core(src);ca,ci=feature_align(src,ctrl,core,2468);ea,ei=feature_align(src,edit,core,2468)
    out={'source':Path(srcpath).name,'source_size':ss,'control_size':cs,'edited_size':es,'control':ci,'edited':ei,'limitation':'no real or synthetic ground truth lesion mask, so precision/recall unknown'}
    if ci['success'] and ei['success']:
        raw,rm,_=r11.measure(src,ctrl,edit,core);aligned,am,_=r11.measure(src,ca,ea,core);union=(rm|am).sum()
        out.update({'raw':raw,'aligned':aligned,'candidate_raw_vs_feature_iou':float((rm&am).sum()/union) if union else None})
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--images',required=True);p.add_argument('--output',required=True);a=p.parse_args();start=time.time();cv2.setNumThreads(2);im=Path(a.images)
    paths=[im/'test8b-arm.png',im/'test10-arm.png'];assert r11.checksum(paths[0])!=r11.checksum(paths[1]);rows=[]
    for path in paths:
        for name,extra in extra_transforms():
            for seed in (18000,18001,18002):rows.append(make_case(path,seed,name,extra))
            print(path.name,name,'done',flush=True)
    out={'protocol':'round14-protocol.md','source_sha256':[r11.checksum(p) for p in paths],'cases':rows,'overall':{},'by_source':{},'by_condition':{},'direct_generated':[],'limitations':['two previously used generated sources','controlled affine synthetic edits and masks','feature matches do not prove clinical label quality','one shared morphology, correlated seeds','pretraining source unknown']}
    for method in ('ecc_affine','sift_ransac'):out['overall'][method]=summary(rows,method)
    for path in paths:
        selected=[z for z in rows if z['source']==path.name];out['by_source'][path.name]={m:summary(selected,m) for m in ('ecc_affine','sift_ransac')}
    for name,_ in extra_transforms():
        selected=[z for z in rows if z['condition']==name];out['by_condition'][name]={m:summary(selected,m) for m in ('ecc_affine','sift_ransac')}
    for src,c,e in [('test8b-arm.png','round12-light-control.png','round12-light-edited.png'),('test10-arm.png','round12-medium-control.png','round12-medium-edited.png')]:out['direct_generated'].append(direct_case(im/src,im/c,im/e))
    out['elapsed_seconds']=round(time.time()-start,2);Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'overall':out['overall'],'by_source':out['by_source'],'direct_generated':out['direct_generated'],'elapsed_seconds':out['elapsed_seconds']},indent=2),flush=True)
if __name__=='__main__':main()
