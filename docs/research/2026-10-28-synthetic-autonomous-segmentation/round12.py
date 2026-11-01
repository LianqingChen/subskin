"""Evaluate small component removal on known synthetic edits, not clinical truth."""
import argparse,importlib.util,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r11',HERE/'round11.py');r11=importlib.util.module_from_spec(s);s.loader.exec_module(r11)


def largest(mask):
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'),connectivity=8)
    if count<=1:return np.zeros_like(mask,dtype=bool)
    return labels==(1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA])))


def synth(src,core,seed):
    rng=np.random.default_rng(seed);h,w=core.shape
    bigsafe=cv2.erode(core.astype('uint8'),np.ones((45,45),np.uint8)).astype(bool)
    smallsafe=cv2.erode(core.astype('uint8'),np.ones((15,15),np.uint8)).astype(bool)
    def center(mask,x1,x2):
        z=np.argwhere(mask);z=z[(z[:,1]>=int(w*x1))&(z[:,1]<int(w*x2))];assert len(z)>0
        return tuple(int(v) for v in z[len(z)//2])
    by,bx=center(bigsafe,.15,.45);sy,sx=center(smallsafe,.60,.85);assert (bx-sx)**2+(by-sy)**2>50**2
    shape_big=np.zeros((h,w),np.uint8);shape_small=np.zeros((h,w),np.uint8)
    cv2.circle(shape_big,(bx,by),18,1,-1);cv2.circle(shape_small,(sx,sy),5,1,-1)
    ab=cv2.GaussianBlur(shape_big.astype('float32'),(0,0),1.2);ass=cv2.GaussianBlur(shape_small.astype('float32'),(0,0),.8)
    alpha=np.maximum(ab,ass);big=(ab>=.8)&core;small=(ass>=.8)&core;ignore=(alpha>.2)&(alpha<.8)&core
    # Known latent positive mask before shared camera transform. Separate noise on control and edited images.
    base=src.astype('float32');changed=np.clip(base+alpha[...,None]*.28*(255-base),0,255)
    def camera(x):
        noisy=np.clip(x+1+rng.normal(0,2,x.shape),0,255).astype('uint8')
        wmat=np.array([[1.,0.,2.],[0.,1.,-1.5]],dtype='float32')
        return cv2.warpAffine(noisy,wmat,r11.SIZE,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    return camera(base),camera(changed),big,small,ignore


def score(mask,big,small,valid):
    pred=mask&valid;gt=(big|small)&valid;tp=int((pred&gt).sum());denom=int(pred.sum());big_n=int((big&valid).sum());small_n=int((small&valid).sum())
    return {'precision':float(tp/denom) if denom else None,'big_recall':float((pred&big).sum()/big_n) if big_n else None,'small_recall':float((pred&small).sum()/small_n) if small_n else None,'predicted_pixels':denom,'big_pixels':big_n,'small_pixels':small_n}


def run_case(path,seed,out):
    src,shape=r11.read(path);core=r11.skin_core(src);control,edited,big,small,ignore=synth(src,core,seed);aligned_ctrl,ci=r11.align(src,control,core);aligned_edit,ei=r11.align(src,edited,core)
    raw,mraw,craw=r11.measure(src,control,edited,core);aligned,m,c=r11.measure(src,aligned_ctrl,aligned_edit,core);valid=core&~ignore;largest_m=largest(m);largest_c=largest(c)
    result={'source':Path(path).name,'source_sha256':r11.checksum(path),'source_size':shape,'seed':seed,'registration_control':ci,'registration_edited':ei,'ignored_pct_of_core':float(100*ignore.sum()/core.sum()),'control_right_raw_pct':raw['control_right_false_positive_pct'],'control_right_aligned_pct':aligned['control_right_false_positive_pct'],'all_components':score(m,big,small,valid),'largest_component_only':score(largest_m,big,small,valid),'control_fp_all_pct':float(100*(c&valid).sum()/valid.sum()),'control_fp_largest_pct':float(100*(largest_c&valid).sum()/valid.sum())}
    Image.fromarray((big|small).astype('uint8')*255).save(out/(Path(path).stem+'-known-core.png'))
    Image.fromarray(m.astype('uint8')*255).save(out/(Path(path).stem+'-pred-all.png'))
    Image.fromarray(largest_m.astype('uint8')*255).save(out/(Path(path).stem+'-pred-largest.png'))
    Image.fromarray(edited).save(out/(Path(path).stem+'-simulated.png'))
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--light',required=True);ap.add_argument('--medium',required=True);ap.add_argument('--out-dir',required=True);a=ap.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    assert r11.checksum(a.light)!=r11.checksum(a.medium)
    result={'protocol':'round12-protocol.md','source_kind':'AI-generated skin; program-generated known edits and noise','cases':[run_case(a.light,12000,out),run_case(a.medium,13000,out)],'limitations':['programmatically imposed positive core, not medical truth','only two synthetic images','core ignores smooth lesion boundary','synthetic perturbations do not model all generative model drift']}
    (out/'known-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
