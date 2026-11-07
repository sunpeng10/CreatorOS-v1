import io


def test_register_cookie_and_role(client):
    r = client.post('/api/auth/register', json={'email': 'first@example.test', 'password': 'Test-Password-482!', 'name': '测试用户'})
    assert r.status_code == 200
    assert r.json()['role'] == 'CLIENT_USER'
    assert 'HttpOnly' in r.headers['set-cookie']
    assert 'password_hash' not in r.text
    assert client.get('/api/auth/me').status_code == 200
    assert client.get('/api/admin/overview').status_code == 403


def test_content_ownership_and_private_upload(client):
    client.post('/api/auth/register', json={'email': 'a@example.test', 'password': 'Test-Password-482!', 'name': 'A'})
    r = client.post('/api/assets/upload', data={'title': 'TEST 测试文稿'}, files={'files': ('测试.md', io.BytesIO('测试正文'.encode()), 'text/markdown')})
    assert r.status_code == 200, r.text
    content, asset = r.json()['id'], r.json()['assets'][0]['id']
    assert client.get('/api/assets/' + asset).status_code == 200
    client.post('/api/auth/logout')
    client.post('/api/auth/register', json={'email': 'b@example.test', 'password': 'Test-Password-482!', 'name': 'B'})
    assert client.get('/api/contents/' + content).status_code == 404
    assert client.get('/api/assets/' + asset).status_code == 404


def test_bad_upload_and_csrf(client):
    client.post('/api/auth/register', json={'email': 'safe@example.test', 'password': 'Test-Password-482!', 'name': 'Safe'})
    r = client.post('/api/assets/upload', data={'title': 'bad'}, files={'files': ('bad.png', b'not a png', 'image/png')})
    assert r.status_code == 422
    r = client.post('/api/assets/upload', data={'title': 'bad'}, files={'files': ('broken.mp4', b'broken video', 'video/mp4')})
    assert r.status_code == 422
    r = client.post('/api/contents', json={'title': 'bad', 'text': 'x'}, headers={'Origin': 'https://evil.example'})
    assert r.status_code == 403


def test_image_album_preserves_order_and_checks_dimensions(client):
    from PIL import Image
    client.post('/api/auth/register', json={'email': 'album@example.test', 'password': 'Test-Password-482!', 'name': 'Album'})
    files = []
    for name, size in [('第一张.png', (12, 14)), ('第二张.png', (15, 11))]:
        stream = io.BytesIO()
        Image.new('RGB', size).save(stream, format='PNG')
        files.append(('files', (name, stream.getvalue(), 'image/png')))
    result = client.post('/api/assets/upload', data={'title': 'TEST 图集', 'text': '配套文案'}, files=files)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload['kind'] == 'album'
    assert [item['position'] for item in payload['assets']] == [0, 1]
    assert [item['metadata']['width'] for item in payload['assets']] == [12, 15]


def test_requested_analysis_title_is_available_for_existing_lists(client):
    client.post('/api/auth/register', json={'email': 'titles@example.test', 'password': 'Test-Password-482!', 'name': 'TEST'})
    content = client.post('/api/contents', json={'title': '雅思口语', 'text': 'TEST'}).json()
    analysis = client.post('/api/analyses', json={'content_id': content['id'], 'mode': 'ai'}).json()
    assert analysis['content_title'] == '雅思口语'
    assert client.get('/api/analyses').json()['items'][0]['content_title'] == '雅思口语'
    assert client.get('/api/dashboard').json()['analyses'][0]['content_title'] == '雅思口语'


def test_work_title_identifies_assets_downloads_and_rejects_duplicates(client):
    from urllib.parse import unquote
    client.post('/api/auth/register', json={'email': 'work-name@example.test', 'password': 'Test-Password-482!', 'name': 'TEST'})
    response = client.post('/api/assets/upload', data={'title': ' 雅思口语 '}, files=[
        ('files', ('4537dd54.md', b'TEST first', 'text/markdown')),
        ('files', ('1090632.txt', b'TEST second', 'text/plain')),
    ])
    assert response.status_code == 200, response.text
    item = response.json()
    assert item['title'] == '雅思口语'
    assert [a['original_name'] for a in item['assets']] == ['雅思口语 · 素材 1.md', '雅思口语 · 素材 2.txt']
    download = client.get('/api/assets/' + item['assets'][0]['id'] + '?download=true')
    assert '雅思口语 · 素材 1.md' in unquote(download.headers['content-disposition'])
    for response in [
        client.post('/api/contents', json={'title': ' 雅思口语 ', 'text': 'TEST'}),
        client.post('/api/assets/upload', data={'title': '雅思口语'}, files={'files': ('repeat.md', b'TEST', 'text/markdown')}),
    ]:
        assert response.status_code == 409, response.text
        assert '作品标题已存在' in response.text
    assert client.get('/api/contents').json()['total'] == 1
    assert client.post('/api/contents', json={'title': '雅思听力', 'text': 'TEST'}).status_code == 200
    client.post('/api/auth/logout')
    client.post('/api/auth/register', json={'email': 'other-work-name@example.test', 'password': 'Test-Password-482!', 'name': 'TEST'})
    assert client.post('/api/contents', json={'title': '雅思口语', 'text': 'TEST'}).status_code == 200
