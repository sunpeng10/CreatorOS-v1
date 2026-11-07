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
