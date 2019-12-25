def test_list_images(client):
    resp1 = client.simulate_get('/images')

    assert resp1.status_code == 200
    assert resp1.headers.get('X-ASGILook-Cache') == 'Miss'
    assert resp1.json == []

    resp2 = client.simulate_get('/images')

    assert resp2.status_code == 200
    assert resp2.headers.get('X-ASGILook-Cache') == 'Hit'
    assert resp2.json == resp1.json
