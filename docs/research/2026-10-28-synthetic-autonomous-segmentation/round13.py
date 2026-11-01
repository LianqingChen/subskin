"""Known synthetic transforms: test if model disagreement catches registration failure."""
import argparse,importlib.util,json,time
from pathlib import Path
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r12',HERE/'round12.py');r12=importlib.util.module_from_spec(sp);sp.loader.exec_module(r12)
sp2=importlib.util.spec_from_file_location('td',HERE/'round12-translation-diagnostic.py');td=importlib.util.module_from_spec(sp2);sp2.loader.exec_module(td)
r11=r12.r11
CONDITIONS=[('translation',0.,1.),('rotate_plus',2.,1.),('rotate_minus',-2.,1.),('scale_down',0.,.98),('scale_up',0.,1.02),('rotate_scale',2.,1.02)]

def homogeneous(a):return np.vstack([np.asarray(a,dtype='float64'),[0.,0.,1.]])
def compose(after,before):return (homogeneous(after)@homogeneous(before))[:2]
def p95_delta(a,b,core):
 y,x=np.nonzero(core);points=np.stack([x,y,np.ones_like(x)]).astype('float64')
 return float(np.quantile(np.linalg.norm((np.asarray(a)-np.asarray(b))@points,axis=0),.95))

def make_case(path,seed,angle,scale):
 src,_=r11.read(path);core=r11.skin_core(src);control,edit,big,small,ignore=r12.synth(src,core,seed)
 extra=cv2.getRotationMatrix2D((256,128),angle,scale).astype('float32')
 control=cv2.warpAffine(control,extra,r11.SIZE,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
 edit=cv2.warpAffine(edit,extra,r11.SIZE,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
 truth=compose(extra,np.array([[1.,0.,2.],[0.,1.,-1.5]],dtype='float32'))
 ca,ci=r11.align(src,control,core);ea,ai=r11.align(src,edit,core);_,ti=td.translation(src,edit,core)
 success=bool(ci['success'] and ai['success']);both=bool(success and ti['success']);geo=p95_delta(ai['matrix'],truth,core) if ai['success'] else None
 disagree=p95_delta(ai['matrix'],ti['matrix'],core) if both else None
 passed=bool(both and disagree<=5.);bad=bool(geo is None or geo>3.)
 rec=None
 if success:
  _,mask,_=r11.measure(src,ca,ea,core);rec=r12.score(mask,big,small,core&~ignore)
 return {'source':Path(path).name,'seed':seed,'angle_deg':angle,'scale':scale,'true_affine':truth.tolist(),'affine_control':ci,'affine_edit':ai,'translation_edit':ti,'geo_p95_px':geo,'disagreement_p95_px':disagree,'baseline_accepted':success,'dual_accepted':passed,'affine_bad':bad,'lesion_scores':rec}

def summarize(rows,accept_key):
 n=len(rows);a=[x for x in rows if x[accept_key]];bad=[x for x in rows if x['affine_bad']];badaccepted=[x for x in a if x['affine_bad']]
 poor=[x for x in a if x['lesion_scores'] is not None and x['lesion_scores']['small_recall']<.5]
 return {'n':n,'accepted':len(a),'coverage_pct':100*len(a)/n,'bad_total':len(bad),'bad_rejected':sum(not x[accept_key] for x in bad),'bad_rejection_pct':None if not bad else 100*sum(not x[accept_key] for x in bad)/len(bad),'bad_among_accepted_pct':None if not a else 100*len(badaccepted)/len(a),'accepted_low_small_recall_count':len(poor)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--light',required=True);p.add_argument('--medium',required=True);p.add_argument('--output',required=True);a=p.parse_args();start=time.time();assert r11.checksum(a.light)!=r11.checksum(a.medium)
 rows=[]
 for path,source in [(a.light,'light'),(a.medium,'medium')]:
  for label,angle,scale in CONDITIONS:
   for seed in (17000,17001,17002):
    row=make_case(path,seed,angle,scale);row['condition']=label;row['source_group']=source;rows.append(row)
   print(source,label,'done',flush=True)
 output={'protocol':'round13-protocol.md','thresholds':{'disagreement_p95_px_max':5.,'true_affine_p95_px_max':3.},'cases':rows,'baseline':summarize(rows,'baseline_accepted'),'dual_guard':summarize(rows,'dual_accepted'),'per_source':{},'per_condition':{},'limitations':['controlled synthetic known affine transforms only','two previously used generated source images','identical program generated lesion geometry','5px threshold not calibrated for real images'],'elapsed_seconds':round(time.time()-start,2)}
 for key in ('light','medium'):
  x=[r for r in rows if r['source_group']==key];output['per_source'][key]={'baseline':summarize(x,'baseline_accepted'),'dual_guard':summarize(x,'dual_accepted')}
 for key,_,_ in CONDITIONS:
  x=[r for r in rows if r['condition']==key];output['per_condition'][key]={'baseline':summarize(x,'baseline_accepted'),'dual_guard':summarize(x,'dual_accepted')}
 Path(a.output).write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'baseline':output['baseline'],'dual_guard':output['dual_guard'],'per_condition':output['per_condition'],'elapsed_seconds':output['elapsed_seconds']},indent=2),flush=True)
if __name__=='__main__':main()
