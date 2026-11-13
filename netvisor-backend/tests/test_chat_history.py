"""Chat history tests: persistence on /ask, GET/export/DELETE chat routes."""

from datetime import UTC, datetime, timedelta

import pytest

from src.config import settings
from src.db.models import AiChatMessage
from src.services.llm import key_resolution
from tests.conftest import auth_cookie


@pytest.fixture(autouse=True)
def clean_llm_settings(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_allow_personal_keys", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_rate_limit_15min", 20)
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_model", "")


@pytest.fixture()
def mock_adapter(monkeypatch):
    """Patch call_provider to a canned success."""
    monkeypatch.setattr(
        key_resolution,
        "call_provider",
        lambda resolved, messages: {
            "text": "**Answer**", "prompt_tokens": 100, "completion_tokens": 20,
        },
    )


def _ask(client, session_id, token, question="What hosts are present?"):
    return client.post(
        f"/api/sessions/{session_id}/ask",
        json={"question": question},
        cookies=auth_cookie(token),
    )


class TestAskPersistence:
    def test_successful_ask_persists_both_messages(
        self, client, user, pcap_session, mock_adapter, monkeypatch, db
    ):
        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        resp = _ask(client, pcap_session[0].id, token)
        assert resp.status_code == 200

        rows = (
            db.query(AiChatMessage)
            .filter(AiChatMessage.session_id == pcap_session[0].id)
            .order_by(AiChatMessage.id.asc())
            .all()
        )
        assert len(rows) == 2
        assert rows[0].role == "user"
        assert rows[0].content == "What hosts are present?"
        assert rows[1].role == "assistant"
        assert rows[1].content == "**Answer**"
        assert rows[0].user_id == user[0].id
        assert rows[0].created_at is not None

    def test_failed_call_persists_nothing(self, client, user, pcap_session, monkeypatch, db):
        from fastapi import HTTPException

        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        def boom(resolved, messages):
            raise HTTPException(status_code=502, detail="Provider returned HTTP 500")

        monkeypatch.setattr(key_resolution, "call_provider", boom)
        resp = _ask(client, pcap_session[0].id, token)
        assert resp.status_code == 502
        assert (
            db.query(AiChatMessage)
            .filter(AiChatMessage.session_id == pcap_session[0].id)
            .count()
            == 0
        )


class TestGetChat:
    def test_history_oldest_first(self, client, user, pcap_session, db):
        _, token = user
        sid = pcap_session[0].id
        base = datetime.now(UTC) - timedelta(minutes=10)
        db.add_all(
            [
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, role="user",
                    content="first question", created_at=base,
                ),
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, role="assistant",
                    content="first answer", created_at=base + timedelta(minutes=1),
                ),
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, role="user",
                    content="second question", created_at=base + timedelta(minutes=2),
                ),
            ]
        )
        db.commit()

        resp = client.get(f"/api/sessions/{sid}/chat", cookies=auth_cookie(token))
        assert resp.status_code == 200
        msgs = resp.json()["messages"]
        assert [m["content"] for m in msgs] == [
            "first question", "first answer", "second question",
        ]
        assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
        assert all(m["created_at"] for m in msgs)

    def test_empty_history(self, client, user, pcap_session):
        _, token = user
        resp = client.get(f"/api/sessions/{pcap_session[0].id}/chat", cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert resp.json() == {"messages": []}

    def test_owner_scoped_403(self, client, user, pcap_session, db):
        import uuid

        from src.auth.jwt import create_access_token
        from src.db.models import User as UserModel

        _, token = user
        other = UserModel(
            username=f"other-{uuid.uuid4().hex[:8]}",
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        )
        db.add(other)
        db.commit()
        other_token = create_access_token(other.id)

        resp = client.get(
            f"/api/sessions/{pcap_session[0].id}/chat", cookies=auth_cookie(other_token)
        )
        assert resp.status_code == 403

    def test_unauthenticated_401(self, client, pcap_session):
        resp = client.get(f"/api/sessions/{pcap_session[0].id}/chat")
        assert resp.status_code == 401

    def test_unknown_session_404(self, client, user):
        _, token = user
        resp = client.get("/api/sessions/nope/chat", cookies=auth_cookie(token))
        assert resp.status_code == 404


class TestExportChat:
    def test_headers_and_format(self, client, user, pcap_session, db):
        _, token = user
        sid = pcap_session[0].id
        db.add_all(
            [
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, role="user",
                    content="What hosts are present?",
                    created_at=datetime(2026, 11, 13, 14, 5, tzinfo=UTC),
                ),
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, role="assistant",
                    content="**Answer**",
                    created_at=datetime(2026, 11, 13, 14, 6, tzinfo=UTC),
                ),
            ]
        )
        db.commit()

        resp = client.get(f"/api/sessions/{sid}/chat/export", cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
        assert resp.headers["content-disposition"] == (
            f'attachment; filename="netvisor-chat-{sid}.md"'
        )
        body = resp.text
        assert body.startswith("# NetVisor chat \u2014 ")
        assert "**[user, 14:05]**\n\nWhat hosts are present?" in body
        assert "**[assistant, 14:06]**\n\n**Answer**" in body

    def test_owner_scoped_403(self, client, user, pcap_session, db):
        import uuid

        from src.auth.jwt import create_access_token
        from src.db.models import User as UserModel

        _, token = user
        other = UserModel(
            username=f"other-{uuid.uuid4().hex[:8]}",
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        )
        db.add(other)
        db.commit()
        other_token = create_access_token(other.id)

        resp = client.get(
            f"/api/sessions/{pcap_session[0].id}/chat/export",
            cookies=auth_cookie(other_token),
        )
        assert resp.status_code == 403

    def test_unauthenticated_401(self, client, pcap_session):
        resp = client.get(f"/api/sessions/{pcap_session[0].id}/chat/export")
        assert resp.status_code == 401


class TestDeleteChat:
    def test_clears_conversation(self, client, user, pcap_session, db):
        _, token = user
        sid = pcap_session[0].id
        db.add(
            AiChatMessage(
                user_id=user[0].id, session_id=sid, role="user",
                content="q", created_at=datetime.now(UTC),
            )
        )
        db.commit()

        resp = client.delete(f"/api/sessions/{sid}/chat", cookies=auth_cookie(token))
        assert resp.status_code == 204
        assert (
            db.query(AiChatMessage).filter(AiChatMessage.session_id == sid).count() == 0
        )

        history = client.get(f"/api/sessions/{sid}/chat", cookies=auth_cookie(token))
        assert history.json() == {"messages": []}

    def test_owner_scoped_403(self, client, user, pcap_session, db):
        import uuid

        from src.auth.jwt import create_access_token
        from src.db.models import User as UserModel

        _, token = user
        other = UserModel(
            username=f"other-{uuid.uuid4().hex[:8]}",
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        )
        db.add(other)
        db.commit()
        other_token = create_access_token(other.id)

        resp = client.delete(
            f"/api/sessions/{pcap_session[0].id}/chat", cookies=auth_cookie(other_token)
        )
        assert resp.status_code == 403

    def test_unauthenticated_401(self, client, pcap_session):
        resp = client.delete(f"/api/sessions/{pcap_session[0].id}/chat")
        assert resp.status_code == 401


class TestSessionDeleteCascadesChat:
    def test_deleting_session_removes_chat_messages(self, client, user, pcap_session, db):
        _, token = user
        sid = pcap_session[0].id
        db.add_all(
            [
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, role="user",
                    content="q", created_at=datetime.now(UTC),
                ),
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, role="assistant",
                    content="a", created_at=datetime.now(UTC),
                ),
            ]
        )
        db.commit()

        resp = client.delete(f"/api/sessions/{sid}", cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert db.query(AiChatMessage).filter(AiChatMessage.session_id == sid).count() == 0
