def test_workspace_overview_lists_match_counts_and_scope(client):
    from app.main import app
    from app.db import get_db
    from app.models import ContentItem, ContentAnalysis, CreatorAccount, Experiment, Organization

    registered = client.post('/api/auth/register', json={'email': 'workspace-overview@example.test', 'password': 'Test-Password-482!', 'name': '创作者'}).json()
    database = app.dependency_overrides[get_db]()
    db = next(database)
    for index in range(7):
        content = ContentItem(organization_id=registered['organization_id'], title=f'研究作品 {index}', data={'platform': '抖音', 'category': '教育'})
        db.add(content); db.flush()
        db.add(ContentAnalysis(organization_id=registered['organization_id'], content_id=content.id, status='SUCCEEDED', mode='local'))
    db.flush()
    db.add(ContentAnalysis(organization_id=registered['organization_id'], content_id=content.id, data={'deleted_at': '2026-11-08T00:00:00+00:00'}))
    db.add_all([
        CreatorAccount(organization_id=registered['organization_id'], name='创作号 A', platform='小红书'),
        CreatorAccount(organization_id=registered['organization_id'], name='创作号 B', platform='抖音'),
        Experiment(organization_id=registered['organization_id'], title='正在运行的实验', status='RUNNING'),
        Experiment(organization_id=registered['organization_id'], title='准备开始的实验', status='PLANNED'),
        Experiment(organization_id=registered['organization_id'], title='已完成的实验', status='COMPLETED'),
    ])
    other = Organization(name='其他工作区'); db.add(other); db.flush()
    private = ContentItem(organization_id=other.id, title='其他工作区私有内容')
    db.add(private); db.flush()
    db.add_all([
        ContentAnalysis(organization_id=other.id, content_id=private.id),
        CreatorAccount(organization_id=other.id, name='其他工作区私有账号', platform='抖音'),
        Experiment(organization_id=other.id, title='其他工作区私有实验', status='RUNNING'),
    ])
    db.commit(); database.close()

    response = client.get('/api/dashboard')
    assert response.status_code == 200, response.text
    overview = response.json()
    assert overview['counts']['contents'] == len(overview['details']['contents']) == 7
    assert overview['counts']['analyses'] == len(overview['details']['analyses']) == 7
    assert overview['counts']['accounts'] == len(overview['details']['accounts']) == 2
    assert overview['counts']['experiments'] == len(overview['details']['experiments']) == 2
    assert len(overview['analyses']) == len(overview['contents']) == 6
    assert {item['status'] for item in overview['details']['experiments']} == {'RUNNING', 'PLANNED'}
    assert all(item['content_title'].startswith('研究作品 ') for item in overview['details']['analyses'])
    assert '其他工作区私有' not in response.text


def test_content_options_and_free_form_account_names_remain_scoped(client):
    client.post('/api/auth/register', json={'email': 'content-options@example.test', 'password': 'Test-Password-482!', 'name': '创作者'})
    assert client.post('/api/accounts', json={'name': '我的创作号', 'platform': '抖音', 'category': '编程教育'}).status_code == 200
    content = client.post('/api/contents', json={'title': '文稿研究', 'text': '内容', 'category': '口语教学', 'account_name': '自由填写账号'})
    assert content.status_code == 200, content.text
    assert content.json()['account_name'] == '自由填写账号'
    assert content.json()['account_id'] is None
    uploaded = client.post('/api/assets/upload', data={'title': '素材研究', 'category': '口语教学', 'account_name': '另一个自由账号'}, files={'files': ('text.md', b'Example text', 'text/markdown')})
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()['account_name'] == '另一个自由账号'
    assert uploaded.json()['account_id'] is None
    assert set(client.get('/api/content-options').json()['categories']) == {'编程教育', '口语教学'}
    client.post('/api/auth/logout')
    client.post('/api/auth/register', json={'email': 'other-options@example.test', 'password': 'Test-Password-482!', 'name': '另一个创作者'})
    assert client.get('/api/content-options').json()['categories'] == []
