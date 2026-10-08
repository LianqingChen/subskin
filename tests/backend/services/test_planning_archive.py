"""Privacy boundaries and historical fidelity of the read-only archive."""
import hashlib
import secrets
from pathlib import Path

import pytest

from web.backend.exceptions import PlanningDocumentError
from web.backend.services.planning_archive import MAX_BYTES, PlanningArchive
from web.backend.utils.planning_metadata import document_date, redact_document


@pytest.fixture
def archive(tmp_path):
    folder = tmp_path / 'docs/research/2026-09-20-example'
    folder.mkdir(parents=True)
    (folder / 'assessment.md').write_text('# 示例研究\n\n可搜索的独特结论。\n', encoding='utf-8')
    (folder / 'task_plan.md').write_text('# 实施计划\n\n- [x] 写出草案\n', encoding='utf-8')
    (folder / 'progress.md').write_text('# 进度\n\n尚未部署\n', encoding='utf-8')
    (tmp_path / 'hermes_plan').mkdir()
    (tmp_path / 'hermes_plan/2026-03-29-old-plan.md').write_text('# 早期方案\n\n旧方案。', encoding='utf-8')
    return PlanningArchive(tmp_path)


def test_group_search_filter_and_dates(archive):
    result = archive.list_documents()
    assert result['stats']['documents'] == 4
    assert result['stats']['topics'] == 2
    match = archive.list_documents(query='独特结论')['items']
    assert len(match) == 1 and match[0]['related_count'] == 3
    assert match[0]['date'] == '2026-09-20'
    assert archive.list_documents(category='progress')['total'] == 1
    assert archive.list_documents(source='hermes_plan', month='2026-03')['total'] == 1
    assert archive.list_documents(month='2026-04')['total'] == 0
    detail = archive.get_document(match[0]['id'])
    assert len(detail['related']) == 3
    assert not any('status' in item for item in detail['related'])


def test_pagination(archive):
    first = archive.list_documents(page=1, page_size=2)
    second = archive.list_documents(page=2, page_size=2)
    assert len(first['items']) == len(second['items']) == 2
    assert {i['id'] for i in first['items']}.isdisjoint(i['id'] for i in second['items'])


def test_refresh_new_changed_deleted(archive):
    result = archive.list_documents(query='独特结论')['items'][0]
    path = archive.root / result['path']
    path.write_text('# 改过的标题\n\n新的内容', encoding='utf-8')
    assert archive.get_document(result['id'])['title'] == '改过的标题'
    added = archive.root / 'docs/research/new.md'
    added.write_text('# 新增', encoding='utf-8')
    assert archive.list_documents(refresh=True)['stats']['documents'] == 5
    path.unlink()
    with pytest.raises(PlanningDocumentError):
        archive.get_document(result['id'])
    assert archive.list_documents(refresh=True)['stats']['documents'] == 4


@pytest.mark.parametrize('path', ['../.env', '/etc/passwd', 'docs/research/../../../.env',
                                  'docs/research/../business/hidden.md', 'docs\\research\\x.md',
                                  'docs/research/a.txt', 'web/backend/app/main.py', 'docs//research/test.md'])
def test_rejects_outside_paths(archive, path):
    with pytest.raises(PlanningDocumentError):
        archive.resolve_document(path)


def test_symlink_and_directory_escape(archive, tmp_path):
    secret = tmp_path / 'private.md'
    secret.write_text('# private', encoding='utf-8')
    (tmp_path / 'docs/research/link.md').symlink_to(secret)
    (tmp_path / 'docs/research/linked').symlink_to(tmp_path, target_is_directory=True)
    result = archive.list_documents(refresh=True)
    assert result['stats']['documents'] == 4
    assert len(result['warnings']) == 1
    for path in ['docs/research/link.md', 'docs/research/linked/private.md']:
        with pytest.raises(PlanningDocumentError):
            archive.resolve_document(path)


def test_symlink_replacement_after_index(archive):
    item = archive.list_documents(query='独特结论')['items'][0]
    path = archive.root / item['path']
    path.unlink()
    outside = archive.root / 'private.md'
    outside.write_text('private', encoding='utf-8')
    path.symlink_to(outside)
    with pytest.raises(PlanningDocumentError):
        archive.get_document(item['id'])


def test_oversized_and_unreadable_are_reported(archive):
    (archive.root / 'docs/research/large.md').write_bytes(b'x' * (MAX_BYTES + 1))
    (archive.root / 'docs/research/binary.md').write_bytes(bytes([255, 254, 253]))
    result = archive.list_documents(refresh=True)
    assert result['stats']['documents'] == 4
    assert len(result['warnings']) == 2


def test_redaction_applies_before_metadata_and_search(archive):
    credential = 'sk-' + secrets.token_hex(20)
    mailbox = secrets.token_hex(6) + '@' + 'example.invalid'
    phone = '1' + '38' + ''.join(str(secrets.randbelow(10)) for _ in range(8))
    path = archive.root / 'docs/research/redaction.md'
    path.write_text('# ' + mailbox + '\n\n' + credential + '\n\n' + phone, encoding='utf-8')
    result = archive.list_documents(refresh=True)
    assert archive.list_documents(query=credential)['total'] == 0
    assert archive.list_documents(query=mailbox)['total'] == 0
    identity = hashlib.sha256(path.relative_to(archive.root).as_posix().encode()).hexdigest()
    combined = str(result) + str(archive.get_document(identity))
    assert credential not in combined and mailbox not in combined and phone not in combined


def test_secret_assignment_and_private_key():
    value = secrets.token_hex(20)
    assert value not in redact_document('API_KEY=' + value)
    assert value not in redact_document('-----BEGIN PRIVATE KEY-----\n' + value + '\n-----END PRIVATE KEY-----')  # pragma: allowlist secret


def test_date_unknown_not_mtime_and_invalid_dates():
    assert document_date('docs/design/example.md', '# 内容') is None
    assert document_date('docs/2026-13-45.md', '# 内容') is None
    assert document_date('docs/2026-09-20.md', '---\ndate: 2026-09-01\n---\n# 内容') == '2026-09-01'


def test_same_dated_topic_across_directories(archive):
    directory = archive.root / 'docs/specs'
    directory.mkdir()
    (directory / '2026-09-20-example-design.md').write_text('# 原始设计', encoding='utf-8')
    (directory / '2026-09-21-example-design.md').write_text('# 次日新设计', encoding='utf-8')
    result = archive.list_documents(refresh=True)
    assert result['stats']['topics'] == 3
    item = archive.list_documents(query='独特结论')['items'][0]
    assert item['related_count'] == 4
    detail = archive.get_document(item['id'])
    assert detail['related'][0]['category'] == 'research'
