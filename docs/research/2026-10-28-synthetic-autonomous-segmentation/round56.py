"""Known-intervention benchmark for synthetic generative-edit mask extraction."""
import argparse,hashlib,json,sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import round11 as base

SOURCES=('train8-arm.png','test22-arm.png','train9-hand.png','test51-leg.png')
METHODS=('raw','ecc','dense')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def make_shapes(core):
    h,w=core.shape;big_safe=cv2.erode(core.astype('uint8'),np.ones((45,45),np.uint8)).astype(bool);small_safe=cv2.erode(core.astype('uint8'),np.ones((15,15),np.uint8)).astype(bool)
    def pick(mask,lo,hi):
        pts=np.argwhere(mask);pts=pts[(pts[:,1]>=int(w*lo))&(pts[:,1]<int(w*hi))]
        if len(pts)==0:raise ValueError('no safe shape location')
        return tuple(map(int,pts[len(pts)//2]))
    by,bx=pick(big_safe,.15,.45);sy,sx=pick(small_safe,.60,.85)
    if (bx-sx)**2+(by-sy)**2<=50**2:raise ValueError('shapes not separated')
    b=np.zeros((h,w),np.uint8);s=np.zeros((h,w),np.uint8);cv2.circle(b,(bx,by),18,1,-1);cv2.circle(s,(sx,sy),5,1,-1)
    ab=cv2.GaussianBlur(b.astype('float32'),(0,0),1.2);ass=cv2.GaussianBlur(s.astype('float32'),(0,0),.8);alpha=np.maximum(ab,ass)
    return alpha,(ab>=.8)&core,(ass>=.8)&core,(alpha>.2)&(alpha<.8)&core

def move(image,scenario,branch):
    h,w=image.shape[:2]
    if scenario=='translation':
        tx,ty=(2.,-1.5) if branch=='control' else (-1.,2.);m=np.array([[1.,0.,tx],[0.,1.,ty]],dtype='float32');return cv2.warpAffine(image,m,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    if scenario=='affine':
        angle,scale,tx,ty=(1.,1.01,1.,-1.) if branch=='control' else (-2.,1.02,-2.,1.5);m=cv2.getRotationMatrix2D(((w-1)/2,(h-1)/2),angle,scale).astype('float32');m[:,2]+=(tx,ty);return cv2.warpAffine(image,m,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    if scenario=='nonrigid':
        yy,xx=np.mgrid[:h,:w].astype('float32');amplitude=.75 if branch=='control' else 2.;mx=xx+amplitude*np.sin(2*np.pi*yy/h);my=yy+amplitude*np.sin(2*np.pi*xx/w);return cv2.remap(image,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    raise ValueError('unknown scenario')

def align(ref,img,core,method):
    if method=='raw':return img,{'success':True}
    if method=='ecc':return base.align(ref,img,core)
    if method=='dense':
        refgray=cv2.cvtColor(ref,cv2.COLOR_RGB2GRAY);movgray=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
        flow=cv2.calcOpticalFlowFarneback(refgray,movgray,None,.5,4,21,5,7,1.5,0)
        if not np.isfinite(flow).all():raise ValueError('nonfinite flow')
        h,w=core.shape;yy,xx=np.mgrid[:h,:w].astype('float32');norm=np.linalg.norm(flow,axis=2);p99=float(np.quantile(norm[core],.99));ok=p99<=20
        aligned=cv2.remap(img,xx+flow[:,:,0],yy+flow[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
        return aligned,{'success':bool(ok),'flow_p99_pixels':p99}
    raise ValueError('unknown method')

def score(pred,big,small,valid):
    p=pred&valid;truth=(big|small)&valid;tp=int((p&truth).sum());pn=int(p.sum());bn=int((big&valid).sum());sn=int((small&valid).sum())
    if not bn or not sn:raise ValueError('missing reference core')
    return {'precision':tp/pn if pn else 0.,'big_recall':int((p&big).sum())/bn,'small_recall':int((p&small).sum())/sn,'predicted_pixels':pn,'big_pixels':bn,'small_pixels':sn}

def choose(cases):
    eligible=[]
    for method in METHODS:
        rows=[r for r in cases if r['method']==method]
        if len(rows)!=24:continue
        if all(r.get('success') and r['control_right_fp_pct']<=1 and r['metrics']['precision']>=.8 and r['metrics']['big_recall']>=.8 and r['metrics']['small_recall']>=.8 for r in rows):eligible.append((min(r['metrics']['small_recall'] for r in rows),-('ecc','dense','raw').index(method),method))
    return max(eligible)[2] if eligible else None

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','images','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();cv2.setNumThreads(2);reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True);paths=[a.images/n for n in SOURCES];assert len({sha(x) for x in paths})==4;cases=[]
    for si,path in enumerate(paths):
        src,shape=base.read(path);core=base.skin_core(src);alpha,big,small,ignore=make_shapes(core);valid=core&~ignore
        for scen_idx,scenario in enumerate(('translation','affine','nonrigid')):
            for strength_idx,strength in enumerate((.12,.28)):
                seed=5600000+si*1000+scen_idx*10+strength_idx;rng=np.random.default_rng(seed);edited=np.clip(src.astype('float32')+alpha[...,None]*strength*(255-src.astype('float32')),0,255).astype('uint8')
                def camera(image,branch):return np.clip(move(image,scenario,branch).astype('float32')+1+rng.normal(0,2,image.shape),0,255).astype('uint8')
                control=camera(src,'control');changed=camera(edited,'edited')
                if si==0 and scen_idx==0 and strength_idx==0:
                    for name,img in [('source',src),('control',control),('intervention',changed),('core',((big|small)*255).astype('uint8')),('ignored',(ignore*255).astype('uint8'))]:Image.fromarray(img).save(a.output_dir/(name+'.png'))
                for method in METHODS:
                    row={'source':path.name,'source_sha256':sha(path),'source_size':shape,'scenario':scenario,'strength':strength,'seed':seed,'method':method}
                    try:
                        c,ci=align(src,control,core,method);e,ei=align(src,changed,core,method);row['control_alignment']=ci;row['edit_alignment']=ei
                        if not (ci['success'] and ei['success']):raise ValueError('alignment gate failed')
                        met,pred,cpred=base.measure(src,c,e,core);row.update(success=True,threshold=met['threshold_l_encoded'],control_right_fp_pct=met['control_right_false_positive_pct'],metrics=score(pred,big,small,valid))
                        if si==0 and scen_idx==0 and strength_idx==0:Image.fromarray((pred*255).astype('uint8')).save(a.output_dir/(method+'-candidate.png'))
                    except Exception as exc:row.update(success=False,error_type=type(exc).__name__)
                    cases.append(row)
        print('completed source',path.name,flush=True)
    assert reg.read_bytes()==before;chosen=choose(cases)
    summary={m:{'cases':sum(x['method']==m for x in cases),'failures':sum(not x.get('success',False) for x in cases if x['method']==m),'eligible':m==chosen} for m in METHODS}
    out={'protocol':'round56-protocol.md','source_sha256':{x.name:sha(x) for x in paths},'selected_method':chosen,'status':'selected_for_further_study' if chosen else 'no_eligible_method','summary':summary,'cases':cases,'registry_sha256':hashlib.sha256(before).hexdigest(),'limitations':['synthetic intervention not medical truth','synthetic motion does not reproduce imagegen drift','source aspect ratio stretched','not a training label']}
    (a.output_dir/'results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'selected':chosen,'summary':summary},indent=2),flush=True)
if __name__=='__main__':main()
