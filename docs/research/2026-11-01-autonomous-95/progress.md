# Progress

2026-11-01: initial active-goal audit. Read current runtime, registry, historical benchmark, prior synthetic research and current primary literature. No active matching experiment process was observed. Preparing reproducible synthetic non-medical input probes; no patient images used.

Completed current-state audit and executed probe_irrelevant_inputs.py in the existing server venv. Output saved to irrelevant-input-probe.json. Created proposed acceptance/design contract; no live services, configurations, patient labels or model registrations modified. Next: inspect candidate repositories and approved evaluation data, then implement and benchmark offline adapters. Goal remains active; 95% is unproven.

Candidate audit and metric implementation turn:
- Inspected GloW-VSNet demo/source through GitHub connector; available checkpoint but 50 cluster channels lack published semantic mapping in demo. No third-party code or weights deployed.
- Verified arXiv:2512.11791 is withdrawn, excluded from efficacy evidence.
- Implemented reference/predicted area percentages and area_ratio_relative_error in ml/rgb_segmentation/metrics.py; included in aggregate with legacy-row compatibility.
- Four added regression tests establish that correct lesion counts can conceal a wrong skin denominator; correct ratios can conceal wrong masks; zero/missing denominators are not perfect scores; missing old metrics do not become zero.
- 8 tests passed. Initial targeted invocation also ran unrelated global src coverage gate and exited nonzero despite all tests passing. Re-ran with coverage scoped to ml.rgb_segmentation.metrics, retaining 67% threshold: 98.78% code coverage, 8 passed; git diff --check passed. Code coverage is not image-recognition accuracy.
- This turn is progress (new verified evidence and offline evaluator implementation). No 95% vision claim; no live service/configuration changes. Next: establish authorized evaluation-only cohort manifests and a local semantic-relevance candidate; use joint mask/ratio/rejection criteria.

Semantic candidate and evaluation-cohort turn:
- Implemented --evaluation-only for validate/evaluate. Explicit evaluation permission is required, training remains separately gated, locked test items required, and hash/subject leakage checks retained. 10 focused dataset/metric tests passed.
- Prepared fixed SigLIP prompts and synthetic negative protocol, downloaded exact revision and verified upstream LFS SHA-256, transferred weights and Python 3.9 wheels via local workstation after remote proxy/direct-download failures. Isolated env /tmp/subskin-semantic95-env; production venv unchanged. Slow pip PID 1434201 was explicitly terminated after offline wheels were available.
- Completed fully offline inference; results and report saved. All model transfer/install/inference processes are terminal, no running experiment to poll.
- User data/metric scope clarified and recorded. No backend deployment or registry changes. Next executable step: provenance/annotation inventory of real licensed datasets and expanded semantic positive/negative validation, then specialist segmentation candidate comparison. Goal remains active and 95% unproven.
