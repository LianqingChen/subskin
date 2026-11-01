"""Post-hoc synthetic rotation/scale stress test, not clinical."""
import argparse,importlib.util,json
from pathlib import Path
import cv2,numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('td',HERE/'round12-translation-diagnostic.py');td=importlib.util.module_from_spec(s);s.loader.exec_module(td)
r12=td.r12;r11=td.r11

def case(path,seed):
 src,_=r11.read(path);core=r11.skin_core(src);control,edited,big,small,ignore=r12.synth(src,core,seed)
 warp=cv2.getRotationMatrix2D((256,128),2.,1.02).astype('float32')
 control=cv2.warpAffine(control,warp,r11.SIZE,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
 edited=cv2.warpAffine(edited,warp,r11.SIZE,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
 result={}
 for name,func in [('affine',r11.align),('translation',td.translation)]:
  ca,ci=func(src,control,core);ea,ei=func(src,edited,core);metrics,mask,_=r11.measure(src,ca,ea,core)
  result[name]={'control_registration':ci,'edited_registration':ei,'control_right_fp_pct':metrics['control_right_false_positive_pct'],'scores':r12.score(mask,big,small,core&~ignore)}
 return {'source':Path(path).name,'added_motion':'2 degrees rotation plus 1.02 scale after translation','methods':result}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--light',required=True);ap.add_argument('--medium',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 data={'status':'post_hoc_exploratory','cases':[case(a.light,12000),case(a.medium,13000)],'limitations':['synthetic known edits and motion only','not a clinical reference','comparison follows observing the prior result']};Path(a.output).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');print(json.dumps(data,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
