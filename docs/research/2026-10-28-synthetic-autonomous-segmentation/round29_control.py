import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]);dataset=Path(sys.argv[2]);base=Path(sys.argv[3]);out=Path(sys.argv[4]);sys.path.insert(0,str(root))
from ml.rgb_segmentation.dataset import validate_manifest
from ml.rgb_segmentation.evaluate import evaluate
v=validate_manifest(dataset,allow_synthetic=True);assert v['synthetic'] and v['counts']=={'train':192,'validation':32,'test':32}
reg=root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert not json.loads(before)['enabled'];out.mkdir(parents=True,exist_ok=False)
for seed in (19,43):
 w=base/f'diverse-{seed}/run/model.pt';report=json.loads((base/f'diverse-{seed}/summary.json').read_text());assert hashlib.sha256(w.read_bytes()).hexdigest()==report['model_sha256']
 evaluate(dataset,w,out/f'{seed}-eval.json',allow_synthetic=True)
 subprocess.run([sys.executable,str(Path(__file__).with_name('round19_policy.py')),'--project-root',str(root),'--manifest',str(dataset),'--weights',str(w),'--output',str(out/f'{seed}-policy.json')],check=True,stdout=subprocess.DEVNULL)
assert before==reg.read_bytes();print('controls evaluated',flush=True)
