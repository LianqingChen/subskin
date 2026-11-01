"""Compare AI edit with no-change control; generates tentative masks only."""
import argparse,hashlib,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw

SIZE=(512,256)

def read(path):
    with Image.open(path) as im:
        rgb=im.convert('RGB');shape=list(rgb.size);data=np.asarray(rgb.resize(SIZE,Image.Resampling.LANCZOS))
    return data,shape

def checksum(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def skin_core(src):
    z=src.astype('int16');cyan=(z[:,:,0]<85)&(z[:,:,1]>120)&(z[:,:,2]>125)&(z[:,:,2]>z[:,:,0]*1.2)
    assert cyan[0,0] and cyan[0,-1] and cyan[-1,0] and cyan[-1,-1]
    skin=(~cyan).astype('uint8');core=cv2.erode(skin,np.ones((7,7),np.uint8)).astype(bool)
    assert .1<core.mean()<.9
    return core

def luma(rgb):return cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB)[:,:,0].astype('float32')

def align(src,img,core):
    template=cv2.cvtColor(src,cv2.COLOR_RGB2GRAY).astype('float32')/255
    moving=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY).astype('float32')/255
    w=np.eye(2,3,dtype='float32')
    try:
        corr,w=cv2.findTransformECC(template,moving,w,cv2.MOTION_AFFINE,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,250,1e-6),core.astype('uint8'),5)
        det=float(np.linalg.det(w[:,:2]));ok=bool(.7<=det<=1.3 and abs(w[0,2])<=SIZE[0]*.2 and abs(w[1,2])<=SIZE[1]*.2 and np.isfinite(w).all())
        aligned=cv2.warpAffine(img,w,SIZE,flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0))
        return aligned,{'success':ok,'corr':float(corr),'determinant':det,'matrix':w.tolist()}
    except cv2.error as e:
        return img,{'success':False,'error':str(e).split('\n')[0]}

def measure(src,control,changed,core):
    h,w=core.shape;left=core.copy();left[:,w//2:]=False;right=core.copy();right[:,:w//2]=False
    ref=luma(src);dc=luma(control)-ref;dt=luma(changed)-ref
    threshold=float(max(3.,np.quantile(dc[left],.999)));testmask=(dt>threshold)&core;controlmask=(dc>threshold)&core
    return {'threshold_l_encoded':threshold,'control_left_calibration_count':int(left.sum()),'control_right_test_count':int(right.sum()),'control_right_false_positive_pct':float(100*controlmask[right].mean()),'candidate_skin_pct':float(100*testmask.sum()/core.sum()),'candidate_pixels':int(testmask.sum())},testmask,controlmask

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--control',required=True);p.add_argument('--edited',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    src,ss=read(a.source);ctrl,cs=read(a.control);edit,es=read(a.edited);core=skin_core(src)
    ca,cinfo=align(src,ctrl,core);ea,einfo=align(src,edit,core)
    raw,mraw,craw=measure(src,ctrl,edit,core);aligned,malign,calign=measure(src,ca,ea,core)
    union=np.logical_or(mraw,malign).sum();iou=float(np.logical_and(mraw,malign).sum()/union) if union else 0.
    gates={'control_raw_fp_at_most_0_5pct':raw['control_right_false_positive_pct']<=.5,'control_aligned_fp_at_most_0_5pct':aligned['control_right_false_positive_pct']<=.5,'raw_candidate_nonempty_under_30pct':0<raw['candidate_skin_pct']<=30,'aligned_candidate_nonempty_under_30pct':0<aligned['candidate_skin_pct']<=30,'candidate_iou_at_least_0_6':iou>=.6,'both_affine_registrations_valid':cinfo['success'] and einfo['success']}
    result={'source_size':ss,'control_size':cs,'edited_size':es,'working_size':list(SIZE),'aspect_ratio_source':ss[0]/ss[1],'aspect_ratio_control':cs[0]/cs[1],'aspect_ratio_edited':es[0]/es[1],'hashes':{k:checksum(v) for k,v in {'source':a.source,'control':a.control,'edited':a.edited}.items()},'source_core_pixels':int(core.sum()),'raw':raw,'aligned':aligned,'candidate_iou':iou,'control_registration':cinfo,'edit_registration':einfo,'gates':gates,'eligible_for_further_label_study':all(gates.values()),'not_a_clinical_label':True,'limitations':['control and edited images are generated, not ground truth','spatial split on one source is correlated','luma difference can be illumination or generative drift','candidate precision and recall are unknown','scaling may distort if aspect differs']}
    Image.fromarray((mraw*255).astype('uint8')).save(out/'raw-mask.png');Image.fromarray((malign*255).astype('uint8')).save(out/'aligned-mask.png')
    canvas=Image.new('RGB',(1024,768),'white');d=ImageDraw.Draw(canvas)
    for idx,(name,array) in enumerate([('source',src),('control',ctrl),('edited',edit),('aligned candidate',np.repeat((malign*255).astype('uint8')[...,None],3,axis=2))]):
        x=(idx%2)*512;y=(idx//2)*384;canvas.paste(Image.fromarray(array),(x,y));d.text((x,y+260),name,fill='black')
    canvas.save(out/'preview.png');(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
