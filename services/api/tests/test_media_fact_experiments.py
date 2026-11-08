"""Focused media, provider search and recommendation tests; no real paid calls."""
import io
import json
from contextlib import contextmanager

import httpx
import pytest


@contextmanager
def database():
    from app.main import app
    from app.db import get_db
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def register(client):
    return client.post('/api/auth/register', json={'email': 'media-facts@example.test', 'password': 'Test-Password-482!', 'name': '创作者'}).json()


def test_webp_preview_and_model_input_ignore_windows_mime_registry(client, monkeypatch):
    from PIL import Image
    from app.models import ContentAsset, ContentItem
    from app.workflow import _media_parts, take_snapshot
    import mimetypes
    monkeypatch.setattr(mimetypes, 'guess_type', lambda *args, **kwargs: (None, None))
    register(client)
    stream = io.BytesIO(); Image.new('RGB', (20, 30), 'green').save(stream, format='WEBP')
    uploaded = client.post('/api/assets/upload', data={'title': '实际图片'}, files={'files': ('123456.webp', stream.getvalue(), 'application/octet-stream')})
    assert uploaded.status_code == 200, uploaded.text
    item = uploaded.json(); asset = item['assets'][0]
    assert asset['mime'] == 'image/webp'
    with database() as db:
        stored = db.get(ContentAsset, asset['id']); stored.mime = 'application/octet-stream'; db.commit()
        parts, _, _ = _media_parts(db, take_snapshot(db, db.get(ContentItem, item['id']), 'ai'))
        assert parts[0]['image_url']['url'].startswith('data:image/webp;base64,')
    assert client.get('/api/contents/' + item['id']).json()['assets'][0]['mime'] == 'image/webp'
    response = client.get('/api/assets/' + asset['id'])
    assert response.headers['content-type'].startswith('image/webp')
    assert response.content == stream.getvalue()


def test_recommendation_creates_matching_experiment_once_and_is_private(client):
    from app.models import ContentAnalysis
    from app.workflow import local_report
    register(client)
    content = client.post('/api/contents', json={'title': '口语视频', 'text': '原始文稿'}).json()
    report = local_report(content).model_dump(); report['tasks'] = ['修正文案的事件日期', '在评论区增加具体提问']
    with database() as db:
        analysis = ContentAnalysis(organization_id=content['organization_id'], content_id=content['id'], status='SUCCEEDED', mode='local', report=report)
        db.add(analysis); db.commit(); identifier = analysis.id
    path = f'/api/analyses/{identifier}/experiments'
    assert client.post(path, json={'task_index': 99}).status_code == 422
    response = client.post(path, json={'task_index': 1})
    assert response.status_code == 200, response.text
    experiment = response.json()
    assert experiment['planned_changes'] == report['tasks'][1]
    assert experiment['hypothesis'] and experiment['observation_window']
    assert experiment['target_metric'] == 'comments'
    assert experiment['analysis_id'] == identifier and experiment['content_id'] == content['id']
    assert client.post(path, json={'task_index': 1}).json()['id'] == experiment['id']
    assert client.get('/api/experiments').json()['total'] == 1
    client.post('/api/auth/logout')
    client.post('/api/auth/register', json={'email': 'stranger-media@example.test', 'password': 'Test-Password-482!', 'name': '其他用户'})
    assert client.post(path, json={'task_index': 1}).status_code == 404


def test_search_transport_exposes_only_provider_sources_and_accounts_for_search_cost():
    from app.mimo import MiMoClient
    from app.schemas_ai import FactCheckDraft
    requests, usage, sources = [], [], []
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'checks': [{'claim': '事件日期', 'status': 'correction', 'finding': '文案日期与来源日期不一致', 'recommendation': '请重点核对', 'source_urls': ['https://example.org/event']}]}), 'annotations': [{'type': 'url_citation', 'url': 'https://example.org/event', 'title': '事件官方说明'}]}}], 'usage': {'prompt_tokens': 50, 'completion_tokens': 30, 'web_search_usage': {'tool_usage': 1}}})
    adapter = MiMoClient(api_key='offline-test-key', transport=httpx.MockTransport(handler))
    adapter.complete_json(FactCheckDraft, [], budget=1, web_search=True, on_sources=sources.extend, on_usage=usage.append)
    assert requests[0]['tools'][0] == {'type': 'web_search', 'max_keyword': 1, 'force_search': True, 'limit': 1}
    assert sources[0]['url'] == 'https://example.org/event'
    assert usage[0]['search_calls'] == 1
    assert usage[0]['estimated_cost'] >= 0.016


def test_fact_check_does_not_treat_uncited_model_memory_as_verified():
    from app.fact_check import grounded_checks
    from app.schemas_ai import FactCheckDraft
    draft = FactCheckDraft(checks=[{'claim': '比赛日期', 'status': 'verified', 'finding': '模型认为日期正确', 'recommendation': '无需修改', 'source_urls': ['https://invented.invalid/page']}])
    result = grounded_checks(draft, [])
    assert result[0].status == 'unverified'
    assert result[0].source_urls == []


def test_incomplete_search_can_be_reanalyzed_without_spending_on_creation(client):
    from app.models import ContentAnalysis, ContentItem
    from app.workflow import cache_key, take_snapshot
    register(client)
    content = client.post('/api/contents', json={'title': '重新核查', 'text': '作品文稿'}).json()
    with database() as db:
        key = cache_key(take_snapshot(db, db.get(ContentItem, content['id']), 'ai'))
        original = ContentAnalysis(organization_id=content['organization_id'], content_id=content['id'], mode='ai', status='SUCCEEDED', cache_key=key, report={'search_status': 'unavailable'})
        db.add(original); db.commit(); original_id = original.id
    fresh = client.post('/api/analyses', json={'content_id': content['id'], 'mode': 'ai'}).json()
    assert fresh['id'] != original_id and fresh['status'] == 'QUEUED'
    assert fresh['task_id'] is None
    with database() as db:
        record = db.get(ContentAnalysis, fresh['id']); record.status = 'SUCCEEDED'; record.report = {'search_status': 'completed'}; db.commit()
    cached = client.post('/api/analyses', json={'content_id': content['id'], 'mode': 'ai'}).json()
    assert cached['cached'] and cached['id'] == fresh['id']


def test_search_budget_blocks_before_request_and_plugin_denial_is_explicit():
    from app.mimo import MiMoClient, MiMoError
    from app.schemas_ai import FactCheckDraft
    calls, usage = [], []
    adapter = MiMoClient(api_key='offline-test-key', transport=httpx.MockTransport(lambda request: calls.append(request) or httpx.Response(403, json={'error': {'code': 'plugin_disabled'}})))
    with pytest.raises(MiMoError) as error:
        adapter.complete_json(FactCheckDraft, [], budget=0.01, web_search=True)
    assert error.value.code == 'BUDGET_EXCEEDED' and calls == []
    with pytest.raises(MiMoError) as error:
        adapter.complete_json(FactCheckDraft, [], budget=1, web_search=True, on_usage=usage.append)
    assert error.value.code == 'WEB_SEARCH_UNAVAILABLE'
    assert len(calls) == 1 and usage[0]['estimated_cost'] == 0


def test_large_video_sends_real_keyframes_instead_of_omitting_visuals(client, tmp_path):
    from PIL import Image
    from app.models import ContentAsset, ContentItem
    from app.workflow import _media_parts, take_snapshot
    register(client)
    content = client.post('/api/contents', json={'title': '长视频画面', 'text': '视频字幕'}).json()
    video = tmp_path / 'large.mp4'
    with video.open('wb') as file:
        file.truncate(36 * 1024 * 1024)
    frame = tmp_path / 'large-frame-0.jpg'; Image.new('RGB', (20, 30), 'blue').save(frame)
    with database() as db:
        original = ContentAsset(organization_id=content['organization_id'], content_id=content['id'], path=str(video), original_name='large.mp4', mime='video/mp4', size=video.stat().st_size, data={'role': 'original', 'metadata': {'duration': 30}})
        keyframe = ContentAsset(organization_id=content['organization_id'], content_id=content['id'], path=str(frame), original_name='关键帧.jpg', mime='image/jpeg', size=frame.stat().st_size, data={'role': 'keyframe', 'timecode': 15})
        db.add_all([original, keyframe]); db.commit()
        parts, notes, tokens = _media_parts(db, take_snapshot(db, db.get(ContentItem, content['id']), 'ai'))
        assert any(part.get('image_url', {}).get('url', '').startswith('data:image/jpeg;base64,') for part in parts)
        assert any('15' in part.get('text', '') for part in parts)
        assert notes and tokens > 0
