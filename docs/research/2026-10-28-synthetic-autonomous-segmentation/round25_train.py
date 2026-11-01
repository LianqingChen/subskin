"""Research-only multi-seed adapter around the unchanged project trainer."""
import argparse
import hashlib
import importlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--project-root', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--seed', type=int, choices=(19, 43), required=True)
    a = p.parse_args()
    started = time.time()
    sys.path.insert(0, str(a.project_root))
    from ml.rgb_segmentation.dataset import validate_manifest
    from ml.rgb_segmentation.evaluate import evaluate
    trainer = importlib.import_module('ml.rgb_segmentation.train')
    doc = validate_manifest(a.manifest, allow_synthetic=True)
    assert doc['synthetic'] and doc['counts'] == {'train': 192, 'validation': 32, 'test': 32}
    registry = a.project_root / 'configs/rgb_segmentation_registry.json'
    before = registry.read_bytes()
    assert not json.loads(before)['enabled']
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        raise ValueError('output directory must be empty')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    originals = [(torch, 'manual_seed', torch.manual_seed), (np.random, 'seed', np.random.seed), (random, 'seed', random.seed)]
    calls = []
    for module, name, original in originals:
        def override(value, module=module, name=name, original=original):
            assert value == 7, f'unexpected initialization seed for {name}'
            setattr(module, name, original)
            calls.append(name)
            return original(a.seed)
        setattr(module, name, override)
    print(f'training {a.manifest.parent.name} seed={a.seed}', flush=True)
    try:
        report = trainer.train(a.manifest, a.output_dir / 'run', epochs=15, side=128, allow_synthetic=True)
    finally:
        for module, name, original in originals:
            setattr(module, name, original)
    assert calls == ['manual_seed', 'seed', 'seed'], calls
    assert report['training_source'] == 'synthetic' and not report['enabled'] and not report['automatic_measurement']
    print(f'evaluating {a.manifest.parent.name} seed={a.seed}', flush=True)
    result = evaluate(a.manifest, a.output_dir / 'run/model.pt', a.output_dir / 'model-eval.json', allow_synthetic=True)
    subprocess.run([sys.executable, str(Path(__file__).with_name('round19_policy.py')), '--project-root', str(a.project_root), '--manifest', str(a.manifest), '--weights', str(a.output_dir / 'run/model.pt'), '--output', str(a.output_dir / 'policy-eval.json')], check=True, stdout=subprocess.DEVNULL)
    policy = json.loads((a.output_dir / 'policy-eval.json').read_text())
    assert registry.read_bytes() == before
    summary = {'seed': a.seed, 'seed_calls': calls, 'manifest_sha256': doc['manifest_sha256'], 'model_sha256': report['sha256'], 'epochs': len(report['history']), 'training_source': report['training_source'], 'enabled': report['enabled'], 'raw': result['summary'], 'groups': result['groups']['body_site'], 'policy': policy['summary'], 'policy_outcomes': policy['outcomes'], 'policy_statuses': policy['policy_statuses'], 'released_area_count': policy['released_area_count'], 'registry_sha256': hashlib.sha256(before).hexdigest(), 'elapsed_seconds': round(time.time() - started, 2)}
    (a.output_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('done', flush=True)


if __name__ == '__main__':
    main()
