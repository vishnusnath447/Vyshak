import sys, os
from uuid import uuid4
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}@example.com"


def test_messages_rest_and_ws():
    # create two users
    r1 = client.post('/api/v1/users', json={"email": unique_email('u1'), "full_name": "User1"})
    assert r1.status_code == 201
    u1 = r1.json()

    r2 = client.post('/api/v1/users', json={"email": unique_email('u2'), "full_name": "User2"})
    assert r2.status_code == 201
    u2 = r2.json()

    # REST create message
    mr = client.post('/api/v1/messages', json={"sender_id": u1['id'], "content": "hello-rest"})
    assert mr.status_code == 201
    m = mr.json()
    assert m['content'] == 'hello-rest'

    # list messages
    lr = client.get('/api/v1/messages')
    assert lr.status_code == 200
    assert any(msg['content'] == 'hello-rest' for msg in lr.json())

    # websocket broadcast between two connected clients
    with client.websocket_connect(f"/api/v1/ws/chat?user_id={u1['id']}") as ws1:
        with client.websocket_connect(f"/api/v1/ws/chat?user_id={u2['id']}") as ws2:
            ws1.send_json({"sender_id": u1['id'], "content": "hi from ws1"})
            data = ws2.receive_json()
            assert data['content'] == 'hi from ws1'

            # persisted
            lr2 = client.get('/api/v1/messages')
            assert any(msg['content'] == 'hi from ws1' for msg in lr2.json())
