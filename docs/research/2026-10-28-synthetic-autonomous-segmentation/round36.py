"""Frozen SAM research heads compared on synthetic contrast data, offline only."""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

EXPECTED_SAM='ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912'
HEADS={'ce0':('round9-heads/arm_and_hand_seed0.pt','801a6bd95b0d645662e832550ad6e40eaabee8169ba2f8b384b1c102255f5c34',0),'ce1':('round9-heads/arm_and_hand_seed1.pt','f0964c5416c316c100adb3e5a02caeb20c40a1f9c195ba574dbc9e232e70516f',1),'dice0':('round10-heads/ce_dice_seed0.pt','47e6cb0a67868494538fa9620944b7154c6213ba8017ff8c970ef06ea576d3bd',0),'dice1':('round10-heads/ce_dice_seed1.pt','6bf8a8360851a4e9d2928a0496a43d317111b9abffe041be852ce426a88a428b',1)}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser()
    for name in ('project-root','manifest','sam-package','sam-weights','research','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(4)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.metrics import score_labels,aggregate
    from web.backend.services.rgb_segmentation.images import png_bytes,canonical_image,frame_information_lost,apply_soft_quality
    from web.backend.services.rgb_segmentation.policy import measure_rgb
    import round7
    doc=validate_manifest(a.manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':192,'validation':32,'test':64}
    assert sha(a.sam_weights)==EXPECTED_SAM
    test_sources={x['source_sha256'] for x in doc['items'] if x['split']=='test'};assert len(test_sources)==2 and test_sources.isdisjoint({x['source_sha256'] for x in doc['items'] if x['split'] in ('train','validation')})
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    heads={}
    for name,(rel,expected,seed) in HEADS.items():
        path=a.research/rel;assert sha(path)==expected;ck=torch.load(str(path),map_location='cpu',weights_only=True);assert ck['model']=='pretrained_sam' and ck['seed']==seed
        net=round7.SamHead().eval();net.load_state_dict(ck['state_dict']);heads[name]=net
    enc=round7.r3.sam_encoder(a.sam_package,a.sam_weights);mean=torch.tensor([123.675,116.28,103.53]).view(1,3,1,1);std=torch.tensor([58.395,57.12,57.375]).view(1,3,1,1)
    data={name:{'raw':[],'policy':[]} for name in heads}
    for i,item in enumerate(x for x in doc['items'] if x['split']=='test'):
        base={'id':item['id'],'subject_id':item['subject_id'],'groups':item['groups']}
        try:
            rgb,truth=load_item(Path(doc['root']),item);assert rgb.shape==(128,128,3)
            x=torch.from_numpy(rgb.copy()).permute(2,0,1).float()[None]/255;x64=F.interpolate(x,size=(64,64),mode='area')
            with torch.inference_mode():feature=enc((F.interpolate(x64,size=(256,256),mode='bilinear',align_corners=False)*255-mean)/std)
            if not torch.isfinite(feature).all():raise ValueError('nonfinite feature')
        except Exception as e:
            for name in heads:
                data[name]['raw'].append({**base,'metrics':None,'error':type(e).__name__});data[name]['policy'].append({**base,'metrics':None,'outcome':'error','error_type':type(e).__name__})
            continue
        for name,head in heads.items():
            raw={**base};policy={**base}
            try:
                with torch.inference_mode():
                    logits=F.interpolate(head(x64,feature),size=(128,128),mode='bilinear',align_corners=False);prob=torch.softmax(logits,1)[0].cpu().numpy()
                if not np.isfinite(prob).all():raise ValueError('nonfinite prediction')
                label=prob.argmax(0).astype('uint8');raw['metrics']=score_labels(label,truth,rgb)
                encoded=png_bytes(rgb);image,_=canonical_image(encoded);assert np.array_equal(image,rgb)
                if frame_information_lost(image):policy.update(outcome='frame_retake',metrics=None)
                else:
                    skin=np.isin(label,[1,2]);uncertain=(prob.max(0)<.7)&skin;masks={'skin':skin,'lesion':(label==2)&~uncertain,'uncertain':uncertain,'excluded':np.isin(label,[3,4])};masks,_=apply_soft_quality(image,masks);decision=measure_rgb(image,masks,encoded,reviewed=False,calibration=None)
                    if decision['status']=='retake_required':policy.update(outcome='policy_retake',metrics=None)
                    else:
                        pred=np.zeros(truth.shape,np.uint8);pred[masks['skin']]=1;pred[masks['lesion']&masks['skin']]=2
                        policy.update(outcome='processed',policy_status=decision['status'],released_area=decision['measurement']['area_percentage'],metrics=score_labels(pred,truth,image))
            except Exception as e:
                raw.setdefault('metrics',None);raw['error']=type(e).__name__;policy.update(metrics=None,outcome='error',error_type=type(e).__name__)
            data[name]['raw'].append(raw);data[name]['policy'].append(policy)
        if (i+1)%8==0:print('encoded',i+1,'/64',flush=True)
    assert reg.read_bytes()==before
    results={}
    for name,rows in data.items():
        groups={}
        for level in ('0','25','50','100'):
            r=[x for x in rows['raw'] if x['groups']['contrast']==level];q=[x for x in rows['policy'] if x['groups']['contrast']==level];assert len(r)==len(q)==16
            groups[level]={'raw':aggregate(r),'policy':aggregate(q),'policy_outcomes':dict(Counter(x['outcome'] for x in q)),'policy_statuses':dict(Counter(x.get('policy_status','not_processed') for x in q)),'released_area_count':sum(x.get('released_area') is not None for x in q),'by_site':{site:aggregate([x for x in r if x['groups']['body_site']==site]) for site in ('arm','hand')}}
        results[name]={'head_sha256':HEADS[name][1],'groups':groups,'rows':rows}
    result={'protocol':'round36-protocol.md','manifest_sha256':doc['manifest_sha256'],'sam_sha256':EXPECTED_SAM,'registry_sha256':hashlib.sha256(before).hexdigest(),'training_source':'synthetic','enabled':False,'models':results,'limitations':['nonstandard SAM input','same observed synthetic test as round34','different training from project U-Net','unknown pretrained source','no clinical truth']}
    (a.output_dir/'results.json').write_text(json.dumps(result,indent=2)+'\n');print('complete',flush=True)
if __name__=='__main__':main()
