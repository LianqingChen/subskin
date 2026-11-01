"""Evaluate frozen SAM ablation heads on untouched synthetic contrast holdout."""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

SAM_HASH='ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','train-manifest','test-manifest','training','sam-package','sam-weights','output-dir'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(4)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.metrics import score_labels,aggregate
    from web.backend.services.rgb_segmentation.images import png_bytes,canonical_image,frame_information_lost,apply_soft_quality
    from web.backend.services.rgb_segmentation.policy import measure_rgb
    import round7
    train=validate_manifest(a.train_manifest,allow_synthetic=True);test=validate_manifest(a.test_manifest,allow_synthetic=True);saved=json.loads((a.training/'training-summary.json').read_text());assert saved['manifest_sha256']==train['manifest_sha256'] and train['synthetic'] and test['synthetic'] and test['counts']=={'train':192,'validation':32,'test':64}
    ident=lambda d,split:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==split]
    for split in ('train','validation'):assert ident(train,split)==ident(test,split)
    assert {i['source_sha256'] for i in train['items'] if i['split'] in ('train','validation')}.isdisjoint({i['source_sha256'] for i in test['items'] if i['split']=='test'})
    assert digest(a.sam_weights)==SAM_HASH and saved['sam_sha256']==SAM_HASH
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert saved['registry_sha256']==hashlib.sha256(before).hexdigest() and not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True);mean=torch.tensor([123.675,116.28,103.53]).view(1,3,1,1);std=torch.tensor([58.395,57.12,57.375]).view(1,3,1,1);allresults={}
    for mode in ('pretrained','random'):
        enc=round7.r3.sam_encoder(a.sam_package,a.sam_weights if mode=='pretrained' else None);heads={}
        for seed in (19,43):
            record=saved['modes'][mode][str(seed)];directory=a.training/(mode+'-'+str(seed))
            for name in ('baseline','gated'):
                weight=directory/(name+'.pt');expected=record['baseline_sha256'] if name=='baseline' else record['gated_sha256']
                if expected is None:assert not weight.exists();continue
                assert digest(weight)==expected;ck=torch.load(str(weight),map_location='cpu',weights_only=True);assert ck['encoder_mode']==mode and ck['seed']==seed and ck['training_source']=='synthetic' and not ck['enabled'];net=round7.SamHead().eval();net.load_state_dict(ck['state_dict']);heads[f'{mode}-{seed}-{name}']=net
        data={name:{'raw':[],'policy':[]} for name in heads}
        for i,item in enumerate(x for x in test['items'] if x['split']=='test'):
            row={'id':item['id'],'subject_id':item['subject_id'],'groups':item['groups']}
            try:
                rgb,truth=load_item(Path(test['root']),item);assert rgb.shape==(128,128,3);x=torch.from_numpy(rgb.copy()).permute(2,0,1).float()[None]/255;x64=F.interpolate(x,size=(64,64),mode='area')
                with torch.inference_mode():feature=enc((F.interpolate(x64,size=(256,256),mode='bilinear',align_corners=False)*255-mean)/std)
                if not torch.isfinite(feature).all():raise ValueError('nonfinite feature')
            except Exception as e:
                for name in heads:data[name]['raw'].append({**row,'metrics':None,'error':type(e).__name__});data[name]['policy'].append({**row,'metrics':None,'outcome':'error','error_type':type(e).__name__})
                continue
            for name,net in heads.items():
                raw={**row};policy={**row}
                try:
                    with torch.inference_mode():logits=F.interpolate(net(x64,feature),size=(128,128),mode='bilinear',align_corners=False);prob=torch.softmax(logits,1)[0].cpu().numpy()
                    if not np.isfinite(prob).all():raise ValueError('nonfinite prediction')
                    label=prob.argmax(0).astype('uint8');raw['metrics']=score_labels(label,truth,rgb);encoded=png_bytes(rgb);image,_=canonical_image(encoded);assert np.array_equal(image,rgb)
                    if frame_information_lost(image):policy.update(outcome='frame_retake',metrics=None)
                    else:
                        skin=np.isin(label,[1,2]);uncertain=(prob.max(0)<.7)&skin;masks={'skin':skin,'lesion':(label==2)&~uncertain,'uncertain':uncertain,'excluded':np.isin(label,[3,4])};masks,_=apply_soft_quality(image,masks);decision=measure_rgb(image,masks,encoded,reviewed=False,calibration=None)
                        if decision['status']=='retake_required':policy.update(outcome='policy_retake',metrics=None)
                        else:
                            pred=np.zeros(truth.shape,np.uint8);pred[masks['skin']]=1;pred[masks['lesion']&masks['skin']]=2;policy.update(outcome='processed',policy_status=decision['status'],released_area=decision['measurement']['area_percentage'],metrics=score_labels(pred,truth,image))
                except Exception as e:raw.setdefault('metrics',None);raw['error']=type(e).__name__;policy.update(metrics=None,outcome='error',error_type=type(e).__name__)
                data[name]['raw'].append(raw);data[name]['policy'].append(policy)
            if (i+1)%16==0:print(mode,'test',i+1,'/64',flush=True)
        for name,rows in data.items():
            groups={}
            for level in ('0','25','50','100'):
                r=[x for x in rows['raw'] if x['groups']['contrast']==level];q=[x for x in rows['policy'] if x['groups']['contrast']==level];assert len(r)==len(q)==16
                groups[level]={'raw':aggregate(r),'policy':aggregate(q),'policy_outcomes':dict(Counter(x['outcome'] for x in q)),'policy_statuses':dict(Counter(x.get('policy_status','not_processed') for x in q)),'released_area_count':sum(x.get('released_area') is not None for x in q),'by_site':{site:aggregate([x for x in r if x['groups']['body_site']==site]) for site in ('arm','hand')}}
            allresults[name]={'groups':groups,'rows':rows}
        del enc
    assert before==reg.read_bytes()
    result={'train_manifest_sha256':train['manifest_sha256'],'test_manifest_sha256':test['manifest_sha256'],'sam_sha256':SAM_HASH,'registry_sha256':hashlib.sha256(before).hexdigest(),'training_source':'synthetic','enabled':False,'models':allresults,'limitations':['nonstandard SAM input','same synthetic generation mechanism','two correlated holdout sources','SAM pretraining source unknown','not clinical truth']}
    (a.output_dir/'results.json').write_text(json.dumps(result,indent=2)+'\n');print('complete',flush=True)
if __name__=='__main__':main()
