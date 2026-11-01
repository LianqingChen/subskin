"""Offline, synthetic-only comparison with current pure inference/policy functions."""
import argparse,hashlib,importlib.util,json,sys,time
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.nn import functional as F
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r9',HERE/'round9.py');r9=importlib.util.module_from_spec(sp);sp.loader.exec_module(r9)
r8=r9.r8;r7=r9.r7;r3=r9.r3


def metrics(masks,truth):
    valid=truth!=255;gt_skin=np.isin(truth,[1,2])&valid;gt_lesion=(truth==2)&valid
    skin=masks['skin']&~masks['excluded']&valid;lesion=masks['lesion']&skin;uncertain=masks['uncertain']&valid
    inter=int((lesion&gt_lesion).sum());tp=inter;fp=int((lesion&~gt_lesion&valid).sum());fn=int((gt_lesion&~lesion).sum())
    skin_dice=float(2*(skin&gt_skin).sum()/(skin.sum()+gt_skin.sum()+1e-9))
    lesion_dice=float(2*tp/(lesion.sum()+gt_lesion.sum()+1e-9)) if gt_lesion.any() else None
    pred_ratio=float(100*lesion.sum()/skin.sum()) if skin.any() else None;truth_ratio=float(100*gt_lesion.sum()/gt_skin.sum()) if gt_skin.any() else None
    return {'skin_dice':skin_dice,'lesion_dice':lesion_dice,'tp':tp,'fp':fp,'fn':fn,'positive':bool(gt_lesion.any()),'valid_pixel_count':int(valid.sum()),'negative_fp_pct_valid':float(100*lesion.sum()/valid.sum()) if not gt_lesion.any() else None,'candidate_share_pct':pred_ratio,'reference_share_pct':truth_ratio,'area_error_pp':abs(pred_ratio-truth_ratio) if pred_ratio is not None and truth_ratio is not None else None,'empty_predicted_skin':not skin.any(),'uncertain_pct_valid':float(100*uncertain.sum()/valid.sum())}


def candidate_masks(logits):
    logits=F.interpolate(logits,size=(512,512),mode='bilinear',align_corners=False);prob=torch.softmax(logits,dim=1)[0].cpu().numpy();labels=prob.argmax(0);skin=np.isin(labels,[1,2]);uncertain=(prob.max(0)<.7)&skin
    return {'skin':skin,'lesion':(labels==2)&~uncertain,'uncertain':uncertain,'excluded':np.isin(labels,[3,4])}


def aggregate(rows):
    processed=[x for x in rows if x['outcome']=='processed'];stats=[x['metrics'] for x in processed];pos=[x['lesion_dice'] for x in stats if x['lesion_dice'] is not None];neg=[x['negative_fp_pct_valid'] for x in stats if x['negative_fp_pct_valid'] is not None];areas=[x['area_error_pp'] for x in stats if x['area_error_pp'] is not None];tp=sum(x['tp'] for x in stats);fp=sum(x['fp'] for x in stats);fn=sum(x['fn'] for x in stats)
    mean=lambda xs:float(np.mean(xs)) if xs else None
    return {'total':len(rows),'processed':len(processed),'outcomes':dict(Counter(x['outcome'] for x in rows)),'branches':dict(Counter(x.get('branch','not_applicable') for x in processed)),'policy_statuses':dict(Counter(x.get('policy_status','unknown') for x in processed)),'positive_count':len(pos),'negative_count':len(neg),'skin_dice_mean':mean([x['skin_dice'] for x in stats]),'lesion_dice_positive_mean':mean(pos),'lesion_micro_precision':float(tp/(tp+fp)) if tp+fp else None,'lesion_micro_recall':float(tp/(tp+fn)) if tp+fn else None,'negative_fp_pct_valid_mean':mean(neg),'area_error_pp_nonempty_mean':mean(areas),'empty_skin_count':sum(x['empty_predicted_skin'] for x in stats),'uncertain_pct_valid_mean':mean([x['uncertain_pct_valid'] for x in stats])}


def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--images',required=True);p.add_argument('--sam-package',required=True);p.add_argument('--sam-weights',required=True);p.add_argument('--output',required=True);p.add_argument('--preview',required=True);a=p.parse_args();start=time.time();torch.set_num_threads(4);sys.path.insert(0,a.project_root)
    from web.backend.services.rgb_segmentation.inference import infer_rgb
    from web.backend.services.rgb_segmentation.images import canonical_image,apply_soft_quality,frame_information_lost,png_bytes
    from web.backend.services.rgb_segmentation.policy import measure_rgb
    registry=Path(a.project_root)/'configs/rgb_segmentation_registry.json';reg_bytes=registry.read_bytes();assert json.loads(reg_bytes)['enabled'] is False;registry_sha=hashlib.sha256(reg_bytes).hexdigest()
    im=Path(a.images);paths=[im/'test17-arm.png',im/'test17-hand.png'];source_hash=[r3.digest(z) for z in paths];assert len(set(source_hash))==2
    train_hash=[r3.digest(im/z) for z in ('train8-arm.png','train9-hand.png')];assert set(source_hash).isdisjoint(train_hash)
    ax,ay=r8.dataset(paths[0],1100000,32);hx,hy=r9.hand_dataset(paths[1],1200000,32);data=torch.cat([ax,hx]);truth=torch.cat([ay,hy]);data_checks={k:r9.check(v,k) for k,v in [('arm',ay),('hand',hy)]}
    preview=Image.new('RGB',(768,384),'white');draw=ImageDraw.Draw(preview)
    for j,xx in enumerate((ax,hx)):
        for i in range(4):
            z=(xx[i].numpy().transpose(1,2,0)*255).astype('uint8');px=i*192;py=j*192;preview.paste(Image.fromarray(z).resize((160,160)),(px,py));draw.text((px,py+161),('arm ' if j==0 else 'hand ')+str(i),fill='black')
    preview.save(a.preview)
    # Fixed model hashes are taken from their archived experiment outputs.
    ref9=json.loads((HERE/'round9-results.json').read_text());ref10=json.loads((HERE/'round10-results.json').read_text());model_specs=[]
    for seed in (0,1):
        for name,folder,file,ref in [('ce','round9-heads',f'arm_and_hand_seed{seed}.pt',next(x for x in ref9['models'] if x['seed']==seed)),('ce_dice','round10-heads',f'ce_dice_seed{seed}.pt',next(x for x in ref10['models'] if x['seed']==seed))]:
            path=HERE/folder/file;sha=r3.digest(path);assert sha==ref['new_head_sha256'];obj=torch.load(path,map_location='cpu',weights_only=True);net=r7.SamHead();net.load_state_dict(obj['state_dict']);net.eval();model_specs.append((f'{name}_{seed}',net,sha))
    encoder=r3.sam_encoder(Path(a.sam_package),Path(a.sam_weights));features=r3.encode(encoder,data);del encoder
    records={name:[] for name in ['current']+[x[0] for x in model_specs]};case_rows=[]
    for idx in range(len(data)):
        typ='arm' if idx<32 else 'hand';rgb64=np.clip(data[idx].numpy().transpose(1,2,0)*255,0,255).astype('uint8');rgb512=cv2.resize(rgb64,(512,512),interpolation=cv2.INTER_NEAREST);lab512=cv2.resize(truth[idx].numpy().astype('uint8'),(512,512),interpolation=cv2.INTER_NEAREST)
        imgbytes=png_bytes(rgb512);rgb,_=canonical_image(imgbytes);assert np.array_equal(rgb,rgb512);hard=bool(frame_information_lost(rgb));case_rows.append({'site':typ,'index':idx,'frame_information_lost':hard,'ignored_pct':float(100*np.mean(lab512==255))})
        if hard:
            for name in records:records[name].append({'site':typ,'outcome':'frame_retake'})
            continue
        candidates={}
        try:
            current,meta=infer_rgb(rgb);candidates['current']=(current,meta.get('source','unknown'))
        except Exception as exc:
            records['current'].append({'site':typ,'outcome':'inference_error','error_type':type(exc).__name__})
        with torch.inference_mode():
            for name,net,_ in model_specs:
                try:candidates[name]=(candidate_masks(net(data[idx:idx+1],features[idx:idx+1])),'offline_candidate_emulation')
                except Exception as exc:records[name].append({'site':typ,'outcome':'inference_error','error_type':type(exc).__name__})
        for name,(mask,branch) in candidates.items():
            try:
                routed,quality=apply_soft_quality(rgb,mask);decision=measure_rgb(rgb,routed,imgbytes,reviewed=False,calibration=None)
                if decision['status']=='retake_required':records[name].append({'site':typ,'outcome':'policy_retake','branch':branch});continue
                proposal={**routed,'lesion':(routed['lesion'] | routed['uncertain']) & routed['skin'] & ~routed['excluded']}
                records[name].append({'site':typ,'outcome':'processed','branch':branch,'policy_status':decision['status'],'blocking_reasons':decision['blocking_reasons'],'quality_status':quality['status'],'metrics':metrics(routed,lab512),'proposal_metrics':metrics(proposal,lab512)})
            except Exception as exc:records[name].append({'site':typ,'outcome':'policy_error','error_type':type(exc).__name__,'branch':branch})
        if idx%8==0:print('processed',idx,'of',len(data),flush=True)
    assert hashlib.sha256(registry.read_bytes()).hexdigest()==registry_sha
    def proposal_aggregate(rows):
        altered=[{**x,'metrics':x['proposal_metrics']} if x['outcome']=='processed' else x for x in rows]
        return aggregate(altered)
    results={name:{'overall':aggregate(rows),'arm':aggregate([x for x in rows if x['site']=='arm']),'hand':aggregate([x for x in rows if x['site']=='hand']),'proposal_diagnostic':proposal_aggregate(rows)} for name,rows in records.items()}
    import mediapipe
    out={'protocol':'round17-protocol.md','source_hashes':source_hash,'training_source_hashes':train_hash,'registry_sha256':registry_sha,'registry_enabled':False,'mediapipe_version':getattr(mediapipe,'__version__','unknown'),'opencv_version':cv2.__version__,'torch_version':torch.__version__,'sam_weights_sha256':r3.digest(a.sam_weights),'model_head_sha256':{x[0]:x[2] for x in model_specs},'data_checks':data_checks,'cases':case_rows,'results':results,'records':records,'limitations':['64x64 synthetic geometry enlarged to 512','local dependencies differ from remote runtime','one generated base per site, correlated cases','synthetic masks are not clinical truth','candidate mapping is offline emulation, not deployed','reviewed false policy intentionally withholds measurement'],'elapsed_seconds':round(time.time()-start,2)}
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'data_checks':data_checks,'results':results,'elapsed_seconds':out['elapsed_seconds']},ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
