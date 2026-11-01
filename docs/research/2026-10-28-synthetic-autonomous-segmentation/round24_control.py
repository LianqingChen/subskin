"""Score the frozen round-20 control on the new synthetic holdout."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]);manifest=Path(sys.argv[2]);weights=Path(sys.argv[3]);out=Path(sys.argv[4]);sys.path.insert(0,str(root))
from ml.rgb_segmentation.dataset import validate_manifest
from ml.rgb_segmentation.evaluate import evaluate
v=validate_manifest(manifest,allow_synthetic=True);assert v['synthetic'] and v['counts']=={'train':192,'validation':32,'test':32}
assert hashlib.sha256(weights.read_bytes()).hexdigest()=='10a4b6d992744669651749fe0b1227eb9e58f187f8ae443f093a0a016262e653'
reg=root/'configs/rgb_segmentation_registry.json';before=reg.read_bytes();assert json.loads(before)['enabled'] is False
out.mkdir(parents=True,exist_ok=False)
evaluate(manifest,weights,out/'model-eval.json',allow_synthetic=True)
subprocess.run([sys.executable,str(Path(__file__).with_name('round19_policy.py')),'--project-root',str(root),'--manifest',str(manifest),'--weights',str(weights),'--output',str(out/'policy-eval.json')],check=True,stdout=subprocess.DEVNULL)
assert reg.read_bytes()==before
print('control done',flush=True)
