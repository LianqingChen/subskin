"""Read-only report diagnostics; emit aggregate categories, never patient data."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

db_path = Path(__file__).resolve().parents[2] / 'data/subskin.db'
db = sqlite3.connect('file:' + str(db_path) + '?mode=ro', uri=True)
summary = Counter()
reasons = Counter()
for raw, in db.execute("SELECT metrics_json FROM skin_reports WHERE report_type='comparison' AND status='completed'"):
    try:
        m = json.loads(raw or '{}')
    except ValueError:
        summary['invalid_json'] += 1
        continue
    p = m.get('pair_metrics') or {}
    e = p.get('evidence') or {}
    summary['reports'] += 1
    summary['status:' + str(p.get('comparison_status', 'missing'))] += 1
    summary['version:' + str(m.get('measurement_version', 'missing'))] += 1
    summary['with_area_change'] += int(p.get('size_change_percent') is not None)
    summary['with_evidence_areas'] += int(e.get('area_a_px') is not None)
    for ref in m.get('refs', [])[:1]:
        summary['source:' + str(ref).split(':')[0]] += 1
    # Map known internal causes, without printing arbitrary stored text.
    for reason in e.get('reasons', []):
        for category in ['测量方法不同', '尚未核对', '范围核对', '共同定位点不足', '共同皮肤纹理不足', '缺少有效', '拍摄角度', '误差过大', '内容重复', '未出现在', '皮肤范围差异']:
            if category in reason:
                reasons[category] += 1
                break
print(json.dumps({'summary':dict(summary), 'reason_categories':dict(reasons)}, ensure_ascii=False, indent=2))
assessment_counts = Counter()
for raw, skin, lesion, user_skin, user_lesion in db.execute('SELECT details, ai_skin_layer, ai_lesion_layer, user_skin_layer, user_lesion_layer FROM vasi_assessments WHERE id IN (SELECT CAST(substr(value,4) AS INTEGER) FROM skin_reports, json_each(metrics_json, \'$.refs\') WHERE report_type=\'comparison\' AND value LIKE \'va:%\')'):
    details = json.loads(raw or '{}')
    measure = details.get('measurement') or {}
    annotation = details.get('annotation') or {}
    for key, value in [('version', measure.get('version')), ('status', measure.get('status')), ('review_state', annotation.get('review_state'))]:
        allowed = ['measured','partial','unavailable','legacy','user_reviewed','unreviewed','auto','ai_suggested','photo-mask-v1','rgb-mask-v1','needs_review']
        assessment_counts[key + ':' + (str(value) if value in allowed or value is None else 'other')] += 1
    assessment_counts['has_skin'] += bool(user_skin or skin)
    assessment_counts['has_lesion'] += bool(user_lesion or lesion)
print(json.dumps({'source_assessments':dict(assessment_counts)}, ensure_ascii=False, indent=2))
# Validate the new owner-only read path under a database-enforced read-only transaction.
from sqlalchemy import text
from web.backend.database.database import SessionLocal
from web.backend.services.report_quantification import supplement_report_quantification
counts = Counter()
with SessionLocal() as session:
    session.execute(text('PRAGMA query_only=ON'))
    rows = session.execute(text("SELECT user_id, report_type, status, metrics_json FROM skin_reports WHERE report_type='comparison' AND status='completed'")).all()
    for owner, kind, status, raw in rows:
        payload = {'report_type':kind, 'status':status, 'metrics':json.loads(raw or '{}')}
        supplement_report_quantification(session, owner, payload)
        photos = (payload['metrics'].get('pair_metrics') or {}).get('photo_measurements') or {}
        counts['reports_checked'] += 1
        counts['with_both_single_photo_area_values'] += all(photos.get(side, {}).get('area_percentage') is not None for side in ('before','after'))
        counts['with_any_single_photo_area_value'] += any(photos.get(side, {}).get('area_percentage') is not None for side in ('before','after'))
print(json.dumps({'read_only_supplement':dict(counts)}, ensure_ascii=False, indent=2))
