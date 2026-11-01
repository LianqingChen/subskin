"""Post-hoc constrained translation exploration; not a preregistered gate."""
import argparse,importlib.util,json
from pathlib import Path
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r12',HERE/'round12.py');r12=importlib.util.module_from_spec(sp);sp.loader.exec_module(r12)
r11=r12.r11

def translation(src,img,core):
 t=cv2.cvtColor(src,cv2.COLOR_RGB2GRAY).astype('float32')/255;m=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY).astype('float32')/255;w=np.eye(2,3,dtype='float32')
 try:
  corr,w=cv2.findTransformECC(t,m,w,cv2.MOTION_TRANSLATION,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,250,1e-6),core.astype('uint8'),5)
  ok=bool(np.isfinite(w).all() and abs(w[0,2])<=r11.SIZE[0]*.2 and abs(w[1,2])<=r11.SIZE[1]*.2)
  return cv2.warpAffine(img,w,r11.SIZE,flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_CONSTANT),{'success':ok,'corr':float(corr),'matrix':w.tolist()}
 except cv2.error as e:return img,{'success':False,'error':str(e).split('\n')[0]}

def run(path,seed):
 src,_=r11.read(path);core=r11.skin_core(src);control,edited,big,small,ignore=r12.synth(src,core,seed);ca,ci=translation(src,control,core);ea,ei=translation(src,edited,core)
 stats,mask,cm=r11.measure(src,ca,ea,core);valid=core&~ignore
 true=np.array([2.,-1.5]);trans_errors={}
 for key,val in [('control',ci),('edited',ei)]:
  if val['success']:
   observed=np.asarray(val['matrix'])[:,2];trans_errors[key]=float(np.linalg.norm(observed-true))
 return {'source':Path(path).name,'registration_control':ci,'registration_edited':ei,'translation_error_pixels':trans_errors,'threshold':stats['threshold_l_encoded'],'control_right_fp_pct':stats['control_right_false_positive_pct'],'all_components':r12.score(mask,big,small,valid),'largest_only':r12.score(r12.largest(mask),big,small,valid)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--light',required=True);p.add_argument('--medium',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 out={'status':'post_hoc_exploratory_not_pre_registered','synthetic_transform':'translation (2,-1.5) working pixels','cases':[run(a.light,12000),run(a.medium,13000)],'limitations':['motion was specifically translation so translation-only assumption matches this synthetic test','no evidence of performance for nonrigid or real edits','not an acceptance decision']}
 Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
