"""Audit probes only. Synthetic controls; no patient images, DB, API, or model calls.
Run with numpy, cv2, Pillow; writes evidence alongside this script.
"""
import sys,io,json,hashlib,dataclasses
from pathlib import Path
import numpy as np
# Optional read-only dependency path for the audit host; numpy stays host-owned.
repo=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(repo))
if (repo/'.venv/lib/python3.9/site-packages').exists():
    sys.path.append(str(repo/'.venv/lib/python3.9/site-packages'))
import cv2
from PIL import Image,ImageDraw
from web.backend.services.vasi_quality import VasiQualityChecker
from web.backend.services.vasi_edge_segmentation import segment_lesions_edge_aware
from web.backend.services.assessment_measurement import measure_layers
from scripts.assessment_benchmark import evaluate
out=Path(__file__).parent/'evidence';out.mkdir(exist_ok=True)
rng=np.random.default_rng(911);h,w=640,800
y,x=np.mgrid[:h,:w];skin=((x-400)/335)**2+((y-320)/270)**2<1
noise=rng.normal(0,4,(h,w,1))
base=np.full((h,w,3),65.,dtype=np.float32)
base[skin]=(np.broadcast_to(np.array([190.,145.,120.]),(h,w,3))+noise)[skin]
base=np.uint8(np.clip(base,0,255))
truth=(x-400)**2+(y-320)**2<90**2
clean=base.copy();clean[truth]=np.clip(np.array([229,221,217])+noise[truth],0,255)
cases=[]
def add(name,img,gt=truth,note=''):
 cases.append((name,np.uint8(np.clip(img,0,255)),gt.copy(),note))
add('clear_control',clean,note='Textured artificial skin ellipse and high contrast circular target')
add('blur_sigma8',cv2.GaussianBlur(clean,(0,0),8),note='Gaussian blur sigma=8; geometry unchanged')
add('dark_20pct',clean.astype(float)*.2,note='RGB multiplied by 0.2')
add('overexposure_clipped',clean.astype(float)*1.6+45,note='RGB clipped after strong exposure increase')
shadow=clean.astype(float);shadow[:,:400]*=.35
add('hard_shadow',shadow,note='Left half multiplied by .35')
glare=clean.copy();gm=(x-425)**2+(y-315)**2<60**2;glare[gm]=255
add('glare_on_target',glare,note='Saturated disk covering target evidence')
gt=(x-400)**2+(y-320)**2<9**2;im=base.copy();im[gt]=[230,225,221];add('small_target_9px',im,gt,'Tiny target with otherwise clear texture')
gt=((x-400)/280)**2+((y-320)/230)**2<1;im=base.copy();im[gt]=np.clip(np.array([229,221,217])+noise[gt],0,255);add('large_target',im,gt,'Large target; surrounding normal artificial skin remains')
a=cv2.GaussianBlur(truth.astype(np.float32),(0,0),14)[:,:,None];im=base*(1-a)+(np.array([207,176,154])+noise)*a
add('diffuse_low_contrast',im,note='Boundary reference is generator geometry, not clinical consensus')
im=clean.copy()
for k in range(18):
 xx=290+k*13;cv2.line(im,(xx,210),(xx+30,425),(35,30,28),2)
add('hair_occlusion',im,note='Artificial dark lines; hidden target is NOT recoverable evidence')
add('normal_control',base,np.zeros((h,w),bool),'No target; false-positive control')
board=np.repeat((((x//8+y//8)%2)*150+40)[:,:,None],3,2)
add('non_skin_checkerboard',board,np.zeros((h,w),bool),'No skin; checks whether texture passes skin gate')
im=base.copy();im[truth]=np.clip(im[truth].astype(float)+65,0,255)
add('bright_normal_distractor',im,np.zeros((h,w),bool),'Artificial brighter normal region, not lesion')
im=cv2.resize(clean,(320,256));gt=cv2.resize(truth.astype(np.uint8),(320,256),interpolation=cv2.INTER_NEAREST).astype(bool)
add('low_resolution',im,gt,'320x256')
records=[];tiles=[]
for name,img,gt,note in cases:
 raw=io.BytesIO();Image.fromarray(img).save(raw,format='PNG')
 q=dataclasses.asdict(VasiQualityChecker().check_all(raw.getvalue()))
 # Force full expected skin ROI for target cases: isolates lesion detector from skin segmentation.
 region=cv2.resize(skin.astype(np.uint8),(img.shape[1],img.shape[0]),interpolation=cv2.INTER_NEAREST).astype(bool)
 if name=='non_skin_checkerboard':region=np.ones(gt.shape,bool)
 seg=segment_lesions_edge_aware(img,region)
 pred=seg['lesion_mask'];metric=evaluate(gt,pred)
 tp=int((gt&pred).sum());fp=int((~gt&pred).sum());fn=int((gt&~pred).sum())
 metric.update(pixel_precision=tp/(tp+fp) if tp+fp else None,pixel_recall=tp/(tp+fn) if tp+fn else None)
 records.append(dict(id=name,input=note,quality=q,formal_gate_allows=q['overall']!='poor',offline_segmentation=metric,source=seg['source'],online_model_tested=False,roi='supplied synthetic region; not production end-to-end'))
 Image.fromarray(img).save(out/f'{name}.png');Image.fromarray(pred.astype(np.uint8)*255).save(out/f'{name}-prediction.png');Image.fromarray(gt.astype(np.uint8)*255).save(out/f'{name}-reference.png')
 visual=Image.fromarray(img).resize((240,192));ov=img.copy();ov[pred]=(.45*ov[pred]+.55*np.array([0,190,170])).astype(np.uint8)
 tile=Image.new('RGB',(480,226),'white');tile.paste(visual,(0,34));tile.paste(Image.fromarray(ov).resize((240,192)),(240,34));d=ImageDraw.Draw(tile);d.text((8,4),f"{name} | Q={q['overall']} | Dice={metric['dice']:.3f}",fill='black');d.text((8,18),'Input                       CV overlay (synthetic probe)',fill='black');tiles.append(tile)
# Mask arithmetic and benchmark controls, no inference.
empty=np.zeros((100,100),bool)
controls={'empty_reference_and_prediction':evaluate(empty,empty)}
files=['web/backend/services/vasi_quality.py','web/backend/services/vasi_edge_segmentation.py','web/backend/services/assessment_measurement.py','web/backend/services/assessment_comparison.py','scripts/assessment_benchmark.py']
report={'scope':'Synthetic module-level probes, NOT clinical accuracy and NOT full online VLM/SAM system','runtime':{'opencv':cv2.__version__,'numpy':np.__version__},'source_sha256':{f:hashlib.sha256((repo/f).read_bytes()).hexdigest() for f in files},'cases':records,'controls':controls}
(out/'offline-probes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
sheet=Image.new('RGB',(960,226*((len(tiles)+1)//2)),(230,230,230))
for i,t in enumerate(tiles):sheet.paste(t,((i%2)*480,(i//2)*226))
sheet.save(out/'synthetic-contact-sheet.png')
print(json.dumps([{'case':r['id'],'quality':r['quality']['overall'],'skin_ok':r['quality']['skin_ok'],'dice':round(r['offline_segmentation']['dice'],3),'area_error_percent':r['offline_segmentation']['area_error_percent'],'pred_px':r['offline_segmentation']['predicted_area_px']} for r in records],indent=2));print('empty controls',controls)
