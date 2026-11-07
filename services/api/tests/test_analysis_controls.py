"""Analysis-history controls and chosen budgets; provider traffic is mocked or unscheduled."""
from contextlib import contextmanager

import httpx
import pytest
from pydantic import BaseModel


@contextmanager
def database():
    from app.main import app
    from app.db import get_db
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def make_analysis(client):
    result = client.post('/api/auth/register', json={'email': 'analysis-controls@example.test', 'password': 'Test-Password-482!', 'name': '测试创作者'})
    assert result.status_code == 200, result.text
    content = client.post('/api/contents', json={'title': '分析控件测试', 'text': '真实输入正文'}).json()
    analysis = client.post('/api/analyses', json={'content_id': content['id'], 'mode': 'ai'}).json()
    return content, analysis


def test_analysis_note_delete_and_privacy_preserve_original_content(client):
    from app.models import ContentAnalysis
    content, analysis = make_analysis(client)
    url = '/api/analyses/' + analysis['id']
    assert client.patch(url, json={'note': 'a' * 3001}).status_code == 422
    assert client.patch(url, json={'note': '  下次调整开头  '}).json()['note'] == '下次调整开头'
    assert client.get('/api/analyses').json()['items'][0]['note'] == '下次调整开头'
    assert client.patch(url, json={'note': None}).json()['note'] == ''
    assert client.get('/api/analyses').json()['items'][0]['note'] == ''
    client.post('/api/auth/logout')
    client.post('/api/auth/register', json={'email': 'unrelated-analysis@example.test', 'password': 'Test-Password-482!', 'name': '另一位创作者'})
    assert client.patch(url, json={'note': '越权'}).status_code == 404
    assert client.delete(url).status_code == 404
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': 'analysis-controls@example.test', 'password': 'Test-Password-482!'})
    assert client.delete(url).json()['deleted'] is True
    assert client.get('/api/analyses').json()['total'] == 0
    assert client.get(url).status_code == 404
    assert client.get(url + '/export').status_code == 404
    assert client.post(url + '/start', json={'confirm_paid': True, 'budget': 2}).status_code == 404
    assert client.get('/api/contents/' + content['id']).status_code == 200
    with database() as db:
        assert db.get(ContentAnalysis, analysis['id']).data['deleted_at']


def test_analysis_delete_blocks_active_tasks_and_delivered_reports(client):
    from app.models import AgentRun, ContentAnalysis, Delivery, Order, Quote
    _, analysis = make_analysis(client)
    with database() as db:
        record = db.get(ContentAnalysis, analysis['id'])
        run = AgentRun(organization_id=record.organization_id, analysis_id=record.id, status='RUNNING')
        db.add(run); db.flush()
        record.task_id = run.id
        db.commit()
        run_id = run.id
    url = '/api/analyses/' + analysis['id']
    assert client.delete(url).status_code == 409
    with database() as db:
        record = db.get(ContentAnalysis, analysis['id'])
        db.get(AgentRun, run_id).status = 'SUCCEEDED'
        record.status = 'SUCCEEDED'
        quote = Quote(organization_id=record.organization_id, amount=0)
        db.add(quote); db.flush()
        order = Order(organization_id=record.organization_id, quote_id=quote.id, amount=0)
        db.add(order); db.flush()
        db.add(Delivery(organization_id=record.organization_id, order_id=order.id, analysis_id=record.id))
        db.commit()
    assert client.delete(url).status_code == 409
    assert client.get(url).status_code == 200


def test_chosen_start_and_retry_budget_is_not_limited_by_old_environment(client, monkeypatch):
    import app.analysis as endpoints
    from app.models import AgentRun, ContentAnalysis
    monkeypatch.setenv('MIMO_API_KEY', 'offline-test-key')
    monkeypatch.setenv('MIMO_MAX_TASK_COST', '1')
    monkeypatch.setattr(endpoints, '_schedule', lambda *args: None)
    _, analysis = make_analysis(client)
    url = '/api/analyses/' + analysis['id']
    assert client.post(url + '/start', json={'confirm_paid': True, 'budget': 10.01}).status_code == 422
    assert client.post(url + '/start', json={'confirm_paid': False, 'budget': 8.75}).status_code == 400
    started = client.post(url + '/start', json={'confirm_paid': True, 'budget': 8.75})
    assert started.status_code == 200, started.text
    assert started.json()['task']['budget'] == 8.75
    task_id = started.json()['task']['id']
    with database() as db:
        run = db.get(AgentRun, task_id)
        run.status, run.cost = 'FAILED', 0.1
        db.get(ContentAnalysis, analysis['id']).status = 'FAILED'
        db.commit()
    assert client.post('/api/tasks/' + task_id + '/retry', json={'budget': 10.01}).status_code == 422
    retried = client.post('/api/tasks/' + task_id + '/retry', json={'budget': 2.34})
    assert retried.status_code == 200, retried.text
    assert retried.json()['budget'] == 2.34


def test_mimo_adapter_reserves_against_chosen_budget_up_to_ten(monkeypatch):
    from app.mimo import MiMoClient, MiMoError
    class Answer(BaseModel):
        summary: str
    monkeypatch.setenv('MIMO_MAX_TASK_COST', '1')
    monkeypatch.setenv('MIMO_INPUT_PRICE_PER_MILLION', '1')
    monkeypatch.setenv('MIMO_OUTPUT_PRICE_PER_MILLION', '4')
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"summary":"完成"}'}}], 'usage': {'prompt_tokens': 2000000, 'completion_tokens': 1}})
    adapter = MiMoClient(api_key='offline-test-key', transport=httpx.MockTransport(handler))
    assert adapter.max_task_cost == 10
    assert adapter.complete_json(Answer, [], budget=3, media_tokens=2000000).summary == '完成'
    with pytest.raises(MiMoError) as error:
        adapter.complete_json(Answer, [], budget=1, media_tokens=2000000)
    assert error.value.code == 'BUDGET_EXCEEDED'
    assert len(calls) == 1
