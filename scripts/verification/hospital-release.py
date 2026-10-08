"""Read-only release verification; no user payloads are stored."""
import json
import re
from pathlib import Path
from urllib.request import urlopen

ROOT = Path('/root/subskin/data/release-candidates/hospital-redesign-20260916')
ROOT.mkdir(parents=True, exist_ok=True)
result = {}
for env, host in [('staging', 'https://staging.subskin.cn'), ('production', 'https://subskin.cn')]:
    def get(path):
        with urlopen(host + path, timeout=20) as response:
            assert response.status == 200
            return response.read()
    version = json.loads(get('/version.json'))
    manifest = json.loads(get('/manifest.webmanifest'))
    html = get('/hospitals').decode()
    assert version['env'] == env
    if env == 'production':
        assert version['buildTime'] == 1789523627301, 'Production unexpectedly changed'
    else:
        assert version['buildTime'] > 1789537720305
        assert manifest['name'] == 'SubSkin [STAGING]'
    assert manifest['background_color'] == '#ffffff'
    assert len(manifest['icons']) >= 9
    assert manifest['theme_color'] == ('#1e293b' if env == 'staging' else '#26A69A')
    assert 'manifest.webmanifest' in html and 'theme-color' in html
    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
    assert assets
    for asset in assets:
        assert get(asset)
    assert len(get('/sw.js')) > 3000
    get('/hospitals/rules')
    if env == 'staging':
        get('/hospitals/treatments')
    result[env] = {'version': version, 'manifest_name': manifest['name'], 'entry_assets': len(assets), 'pwa_ok': True}
with urlopen('http://127.0.0.1:8000/api/health', timeout=10) as response:
    result['backend_health'] = json.load(response)
assert result['backend_health']['status'] == 'ok'
result['backend_activation'] = 'pending_user_confirmation'
(ROOT / 'release-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False, indent=2))
