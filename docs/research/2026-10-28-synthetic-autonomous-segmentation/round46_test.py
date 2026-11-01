"""Evaluate frozen validation-selected synthetic component filter on new sources."""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

SELECTED_SCAN_SHA='923d7ebbf197cf7f2fd6d14769bd156e563ea76db4781662512d3b5a0408c7d8'

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','train-manifest','test-manifest','validation','weights','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(2)
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.metrics import score_labels,aggregate
    from web.backend.services.rgb_segmentation.images import png_bytes,canonical_image,frame_information_lost,apply_soft_quality
    from web.backend.services.rgb_segmentation.policy import measure_rgb
    from round46 import filter_components
    scanbytes=a.validation.read_bytes();assert hashlib.sha256(scanbytes).hexdigest()==SELECTED_SCAN_SHA;selection=json.loads(scanbytes)['models']['prior-43'];assert selection['status']=='selected' and selection['selected_min_area']==256
    h=hashlib.sha256(a.weights.read_bytes()).hexdigest();assert h==selection['weights_sha256'];train=validate_manifest(a.train_manifest,allow_synthetic=True);test=validate_manifest(a.test_manifest,allow_synthetic=True)
    assert train['synthetic'] and test['synthetic'] and test['counts']=={'train':384,'validation':160,'test':64}
    ident=lambda d,s:[(x['id'],x['image_sha256'],x['mask_sha256']) for x in d['items'] if x['split']==s]
    for split in ('train','validation'):assert ident(train,split)==ident(test,split)
    assert {i['source_sha256'] for i in train['items'] if i['split'] in ('train','validation')}.isdisjoint({i['source_sha256'] for i in test['items'] if i['split']=='test'})
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];net=torch.jit.load(str(a.weights)).eval();data={k:{'raw':[],'policy':[]} for k in ('baseline','filtered')}
    for item in test['items']:
        if item['split']!='test':continue
        base={'id':item['id'],'subject_id':item['subject_id'],'groups':item['groups']}
        try:
            rgb,truth=load_item(Path(test['root']),item);x=torch.from_numpy(rgb.copy()).permute(2,0,1).float()[None]/255
            with torch.inference_mode():prob=torch.softmax(net(x),1)[0].cpu().numpy()
            if prob.shape!=(5,128,128) or not np.isfinite(prob).all():raise ValueError('invalid probabilities')
        except Exception as exc:
            for name in data:data[name]['raw'].append({**base,'metrics':None,'error':type(exc).__name__});data[name]['policy'].append({**base,'metrics':None,'outcome':'error','error_type':type(exc).__name__})
            continue
        for name,area in [('baseline',1),('filtered',256)]:
            raw={**base,'reference_lesion_pixels':int((truth==2).sum())};policy={**base,'reference_lesion_pixels':int((truth==2).sum())}
            try:
                label=filter_components(prob.argmax(0).astype('uint8'),area);raw['metrics']=score_labels(label,truth,rgb);encoded=png_bytes(rgb);image,_=canonical_image(encoded);assert np.array_equal(image,rgb)
                if frame_information_lost(image):policy.update(outcome='frame_retake',metrics=None)
                else:
                    skin=np.isin(label,[1,2]);uncertain=(prob.max(0)<.7)&skin;masks={'skin':skin,'lesion':(label==2)&~uncertain,'uncertain':uncertain,'excluded':np.isin(label,[3,4])};masks,_=apply_soft_quality(image,masks);decision=measure_rgb(image,masks,encoded,reviewed=False,calibration=None)
                    if decision['status']=='retake_required':policy.update(outcome='policy_retake',metrics=None)
                    else:
                        pred=np.zeros(truth.shape,np.uint8);pred[masks['skin']]=1;pred[masks['lesion']&masks['skin']]=2;policy.update(outcome='processed',policy_status=decision['status'],released_area=decision['measurement']['area_percentage'],metrics=score_labels(pred,truth,image))
            except Exception as exc:raw.setdefault('metrics',None);raw['error']=type(exc).__name__;policy.update(metrics=None,outcome='error',error_type=type(exc).__name__)
            data[name]['raw'].append(raw);data[name]['policy'].append(policy)
    assert before==reg.read_bytes();result={}
    for name,rows in data.items():
        groups={}
        for level in ('0','25','50','100'):
            raw=[x for x in rows['raw'] if x['groups']['contrast']==level];pol=[x for x in rows['policy'] if x['groups']['contrast']==level];assert len(raw)==len(pol)==16
            small=[x for x in raw if 0<x['reference_lesion_pixels']<=64]
            groups[level]={'raw':aggregate(raw),'small_count':len(small),'small_raw':aggregate(small) if small else None,'policy':aggregate(pol),'policy_outcomes':dict(Counter(x['outcome'] for x in pol)),'policy_statuses':dict(Counter(x.get('policy_status','not_processed') for x in pol)),'released_area_count':sum(x.get('released_area') is not None for x in pol),'by_site':{site:aggregate([x for x in raw if x['groups']['body_site']==site]) for site in ('arm','hand')}}
        result[name]={'groups':groups,'rows':rows}
    if a.output.exists():raise ValueError('output exists')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'validation_sha256':SELECTED_SCAN_SHA,'weights_sha256':h,'test_manifest_sha256':test['manifest_sha256'],'registry_sha256':hashlib.sha256(before).hexdigest(),'selected_area':256,'models':result,'limitations':['validation reused in training and selection','synthetic correlated sources','minimum area is not calibrated physical size','no clinical truth']},indent=2)+'\n');print('heldout complete',flush=True)
if __name__=='__main__':main()
