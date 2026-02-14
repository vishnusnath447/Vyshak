from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models.user import User
from app.models.message import Message
from app.schemas.user import UserCreate, UserRead
from app.schemas.message import MessageCreate, MessageRead

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/users", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email, full_name=payload.full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=List[UserRead])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).limit(100).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# --- Messages (REST + WebSocket demo) -------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: Dict[str, Any]):
        living = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
                living.append(connection)
            except Exception:
                # drop dead connections
                try:
                    connection.close()
                except Exception:
                    pass
        self.active_connections = living


manager = ConnectionManager()


@router.post("/messages", response_model=MessageRead, status_code=201)
async def create_message(payload: MessageCreate, db: Session = Depends(get_db)):
    # validate sender exists
    user = db.query(User).filter(User.id == payload.sender_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Sender not found")
    msg = Message(sender_id=payload.sender_id, content=payload.content)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # notify websocket clients (if any)
    await manager.broadcast({
        "id": msg.id,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
    })

    return msg


@router.get("/messages", response_model=List[MessageRead])
def list_messages(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Message).order_by(Message.created_at.asc()).limit(limit).all()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, user_id: int | None = None):
    """Simple in-memory WebSocket chat. Clients should send JSON {sender_id, content}.
    Messages are stored to the DB and broadcast to all connected clients.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            sender_id = data.get("sender_id")
            content = data.get("content")
            if not sender_id or not content:
                await websocket.send_json({"error": "sender_id and content required"})
                continue

            # persist
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == sender_id).first()
                if not user:
                    await websocket.send_json({"error": "sender not found"})
                    continue
                msg = Message(sender_id=sender_id, content=content)
                db.add(msg)
                db.commit()
                db.refresh(msg)

                payload = {
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
                await manager.broadcast(payload)
            finally:
                db.close()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/chat", response_class=HTMLResponse)
def chat_ui():
    """Minimal chat UI that uses the WebSocket endpoint and the messages REST API."""
    return """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Vyshak — Chat demo</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 20px }
      #messages { border: 1px solid #ddd; height: 300px; overflow: auto; padding: 8px }
      .msg { margin: 6px 0 }
      .sender { font-weight: 600 }
    </style>
  </head>
  <body>
    <h3>Vyshak — Chat (demo)</h3>
    <p>Select a user and send messages. Messages are broadcast via WebSocket and persisted.</p>

    <label for="user">User:</label>
    <select id="user"></select>
    <div id="messages"></div>

    <div style="margin-top:8px">
      <input id="text" style="width:70%" placeholder="Type a message..." />
      <button id="send">Send</button>
    </div>

    <script>
      const userSelect = document.getElementById('user');
      const messagesEl = document.getElementById('messages');
      const input = document.getElementById('text');
      const sendBtn = document.getElementById('send');

      async function fetchUsers() {
        const r = await fetch('/api/v1/users');
        const users = await r.json();
        users.forEach(u => {
          const opt = document.createElement('option');
          opt.value = u.id; opt.text = u.full_name || u.email;
          userSelect.appendChild(opt);
        });
      }

      async function loadHistory() {
        const r = await fetch('/api/v1/messages');
        const msgs = await r.json();
        msgs.forEach(appendMsg);
      }

      function appendMsg(m) {
        const d = document.createElement('div');
        d.className = 'msg';
        const when = new Date(m.created_at).toLocaleTimeString();
        d.innerHTML = `<span class="sender">User ${m.sender_id}</span>: ${m.content} <span style="color:#888">${when}</span>`;
        messagesEl.appendChild(d);
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }

      const wsProto = (location.protocol === 'https:') ? 'wss://' : 'ws://';
      const ws = new WebSocket(wsProto + location.host + '/api/v1/ws/chat');
      ws.onmessage = (ev) => {
        try { const msg = JSON.parse(ev.data); appendMsg(msg); } catch(e){}
      };

      sendBtn.onclick = () => {
        const sender_id = Number(userSelect.value);
        const content = input.value.trim();
        if (!sender_id || !content) return;
        ws.send(JSON.stringify({ sender_id, content }));
        input.value = '';
      };

      (async function init(){
        await fetchUsers();
        await loadHistory();
      })();
    </script>
  </body>
</html>
"""
