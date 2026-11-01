"""Post-hoc, frozen-model synthetic holdout comparison; no deployment."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--project-root', type=Path, required=True)
    p.add_argument('--test-manifest', type=Path, required=True)
    p.add_argument('--train-manifest', type=Path, required=True)
    p.add_argument('--weights', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.project_root))
    from ml.rgb_segmentation.dataset import validate_manifest
    from ml.rgb_segmentation.evaluate import evaluate
    train = validate_manifest(a.train_manifest, allow_synthetic=True)
    test = validate_manifest(a.test_manifest, allow_synthetic=True)
    assert train['synthetic'] and test['synthetic']
    assert test['counts'] == {'train': 192, 'validation': 32, 'test': 32}
    sources_train = {i['source_sha256'] for i in train['items'] if i['split'] in ('train', 'validation')}
    sources_test = {i['source_sha256'] for i in test['items'] if i['split'] == 'test'}
    assert len(sources_test) == 2 and sources_train.isdisjoint(sources_test)
    assert sha(a.weights) == '33685240a37c4490064287a7941b103fd78d3e5353e7d7de7486cf315106f1bd'
    registry = a.project_root / 'configs/rgb_segmentation_registry.json'
    before = registry.read_bytes()
    assert json.loads(before)['enabled'] is False
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        raise ValueError('output directory must be empty')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    raw = evaluate(a.test_manifest, a.weights, a.output_dir / 'negative-eval.json', allow_synthetic=True)
    policy = Path(__file__).with_name('round19_policy.py')
    subprocess.run([sys.executable, str(policy), '--project-root', str(a.project_root), '--manifest', str(a.test_manifest), '--weights', str(a.weights), '--output', str(a.output_dir / 'negative-policy.json')], check=True)
    assert registry.read_bytes() == before
    summary = {'kind': 'post_hoc_synthetic_only', 'test_manifest_sha256': test['manifest_sha256'], 'train_manifest_sha256': train['manifest_sha256'], 'weights_sha256': sha(a.weights), 'test_sources': sorted(sources_test), 'registry_sha256': hashlib.sha256(before).hexdigest(), 'summary': raw['summary'], 'body_site': raw['groups']['body_site']}
    (a.output_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
