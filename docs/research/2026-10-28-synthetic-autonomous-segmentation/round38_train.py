"""Controlled SAM pretraining ablation on synthetic images; research only."""
import argparse,hashlib,json,sys,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

SAM_HASH='ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for x in iter(lambda:f.read(1048576),b''):h.update(x)
    return h.hexdigest()

def weighted_training_loss(logits, target, original_loss):
    weights=logits.new_tensor([1.,1.,3.,1.,1.])
    return original_loss(logits,target)-F.cross_entropy(logits,target,ignore_index=255)+F.cross_entropy(logits,target,weight=weights,ignore_index=255)

def state_hash(model):
    h=hashlib.sha256()
    for k,v in sorted(model.state_dict().items()):h.update(k.encode());h.update(v.detach().cpu().numpy().tobytes())
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser()
    for n in ('project-root','manifest','sam-package','sam-weights','output-dir','prior-summary'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.project_root));torch.set_num_threads(4);started=time.time();prior=json.loads(a.prior_summary.read_text())
    from ml.rgb_segmentation.dataset import validate_manifest,load_item
    from ml.rgb_segmentation.train import loss
    from round26 import validation_stats
    import round7
    doc=validate_manifest(a.manifest,allow_synthetic=True);assert doc['synthetic'] and doc['counts']=={'train':192,'validation':32,'test':32} and digest(a.sam_weights)==SAM_HASH and prior['manifest_sha256']==doc['manifest_sha256'] and prior['sam_sha256']==SAM_HASH
    reg=a.project_root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):raise ValueError('nonempty output')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    data={}
    for split in ('train','validation'):
        images=[];targets=[]
        for item in doc['items']:
            if item['split']!=split:continue
            rgb,truth=load_item(Path(doc['root']),item);im=torch.from_numpy(rgb.copy()).permute(2,0,1).float()[None]/255;target=torch.from_numpy(truth.astype('int64').copy())[None,None].float()
            images.append(F.interpolate(im,size=(64,64),mode='area')[0]);targets.append(F.interpolate(target,size=(64,64),mode='nearest')[0,0].long())
        data[split]=(torch.stack(images),torch.stack(targets))
    xtrain,ytrain=data['train'];xval,yval=data['validation'];assert len(xtrain)==192 and len(xval)==32
    allx=torch.cat([xtrain,xval]);initials={};result={'manifest_sha256':doc['manifest_sha256'],'sam_sha256':SAM_HASH,'encoder_input':'64 to 256, interpolated positional embedding','samples':{'train':192,'validation':32},'modes':{},'training_source':'synthetic','enabled':False,'automatic_measurement':False,'training_loss':'weighted CE class2=3 plus original Dice; validation unweighted'}
    for mode in ('pretrained','random'):
        print('loading encoder',mode,flush=True);enc=round7.r3.sam_encoder(a.sam_package,a.sam_weights if mode=='pretrained' else None);features=round7.r3.encode(enc,allx);del enc;ft,fv=features[:192],features[192:];assert torch.isfinite(features).all();result['modes'][mode]={}
        for seed in (19,43):
            torch.manual_seed(seed);net=round7.SamHead();initial=state_hash(net)
            if seed in initials:assert initials[seed]==initial
            assert prior['modes'][mode][str(seed)]['initial_state_sha256']==initial
            initials[seed]=initial;opt=torch.optim.AdamW(net.parameters(),lr=.001);rng=np.random.default_rng(seed);best=float('inf');best_gate=float('inf');stale=0;history=[];gate_epoch=None;target=a.output_dir/(mode+'-'+str(seed));target.mkdir()
            for epoch in range(1,16):
                net.train();trainloss=0.
                for indices in rng.permutation(192).reshape(-1,8):
                    opt.zero_grad();logits=net(xtrain[indices],ft[indices]);value=weighted_training_loss(logits,ytrain[indices],loss);value.backward();opt.step();trainloss+=float(value.detach())
                net.eval();vl=0.;pairs=[]
                with torch.inference_mode():
                    for i in range(32):
                        logits=net(xval[i:i+1],fv[i:i+1]);vl+=float(loss(logits,yval[i:i+1]));pairs.append((logits.argmax(1),yval[i:i+1]))
                vl/=32
                if not np.isfinite(vl):raise ValueError('nonfinite validation loss')
                stats=validation_stats(pairs);passes=stats['recall']>=.30 and stats['false_positives']<=2
                history.append({'epoch':epoch,'train_loss':trainloss/24,'validation_loss':vl,'validation':stats,'gate_pass':passes})
                checkpoint={'state_dict':net.state_dict(),'encoder_mode':mode,'seed':seed,'epoch':epoch,'initial_state_sha256':initial,'training_source':'synthetic','enabled':False,'automatic_measurement':False}
                if vl<best:best=vl;stale=0;torch.save(checkpoint,target/'baseline.pt')
                else:stale+=1
                if passes and vl<best_gate:best_gate=vl;gate_epoch=epoch;torch.save(checkpoint,target/'gated.pt')
                print(mode,seed,'epoch',epoch,'pass',passes,flush=True)
                if stale>=5:break
            result['modes'][mode][str(seed)]={'history':history,'initial_state_sha256':initial,'baseline_sha256':digest(target/'baseline.pt'),'gated_epoch':gate_epoch,'gated_sha256':digest(target/'gated.pt') if gate_epoch else None,'status':'selected' if gate_epoch else 'no_eligible_checkpoint'}
        del features,ft,fv
    assert reg.read_bytes()==before
    result['registry_sha256']=hashlib.sha256(before).hexdigest();result['elapsed_seconds']=round(time.time()-started,2)
    (a.output_dir/'training-summary.json').write_text(json.dumps(result,indent=2)+'\n');print('training complete',flush=True)
if __name__=='__main__':main()
