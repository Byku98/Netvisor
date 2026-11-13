"""Multi-chat tests: /ask auto-create + append, chats list, per-chat CRUD."""

from datetime import UTC, datetime, timedelta

import pytest

from src.config import settings
from src.db.models import AiChat, AiChatMessage, AiUsage
from src.db.models import Session as SessionModel
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


def _ask(client, session_id, token, question="What hosts are present?", chat_id=None):
    body = {"question": question}
    if chat_id is not None:
        body["chat_id"] = chat_id
    return client.post(
        f"/api/sessions/{session_id}/ask",
        json=body,
        cookies=auth_cookie(token),
    )


def _other_user(db):
    import uuid

    from src.auth.jwt import create_access_token
    from src.db.models import User as UserModel

    suffix = uuid.uuid4().hex[:8]
    other = UserModel(
        username=f"other-{suffix}", email=f"other-{suffix}@example.com"
    )
    db.add(other)
    db.commit()
    return other, create_access_token(other.id)


class TestAskPersistence:
    def test_ask_without_chat_id_auto_creates_chat(
        self, client, user, pcap_session, mock_adapter, monkeypatch, db
    ):
        u, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        resp = _ask(client, pcap_session[0].id, token)
        assert resp.status_code == 200

        data = resp.json()
        chat = db.get(AiChat, data["chat_id"])
        assert chat is not None
        assert chat.user_id == u.id
        assert chat.session_id == pcap_session[0].id
        assert chat.title == "What hosts are present?"

        rows = (
            db.query(AiChatMessage)
            .filter(AiChatMessage.chat_id == chat.id)
            .order_by(AiChatMessage.id.asc())
            .all()
        )
        assert len(rows) == 2
        assert rows[0].role == "user"
        assert rows[0].content == "What hosts are present?"
        assert rows[1].role == "assistant"
        assert rows[1].content == "**Answer**"
        assert rows[0].user_id == u.id
        assert rows[0].created_at is not None

    def test_ask_records_chat_id_in_ai_usage(
        self, client, user, pcap_session, mock_adapter, monkeypatch, db
    ):
        """Both auto-created and appended /ask calls tag their ai_usage row."""
        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        first = _ask(client, pcap_session[0].id, token, question="First question")
        assert first.status_code == 200
        chat_id = first.json()["chat_id"]

        second = _ask(
            client, pcap_session[0].id, token, question="Second question", chat_id=chat_id
        )
        assert second.status_code == 200

        rows = (
            db.query(AiUsage)
            .filter(AiUsage.user_id == user[0].id)
            .order_by(AiUsage.id.asc())
            .all()
        )
        assert len(rows) == 2
        assert all(r.chat_id == chat_id for r in rows)

    def test_ask_title_truncated_to_50_chars(
        self, client, user, pcap_session, mock_adapter, monkeypatch, db
    ):
        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        question = "x" * 80
        resp = _ask(client, pcap_session[0].id, token, question=question)
        assert resp.status_code == 200
        chat = db.get(AiChat, resp.json()["chat_id"])
        assert chat.title == "x" * 50

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
        assert db.query(AiChat).filter(AiChat.session_id == pcap_session[0].id).count() == 0


class TestAskAppend:
    def test_append_to_given_chat_id(
        self, client, user, pcap_session, mock_adapter, monkeypatch, db
    ):
        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        first = _ask(client, pcap_session[0].id, token, question="First question")
        assert first.status_code == 200
        chat_id = first.json()["chat_id"]

        second = _ask(
            client, pcap_session[0].id, token, question="Second question", chat_id=chat_id
        )
        assert second.status_code == 200
        assert second.json()["chat_id"] == chat_id

        chat = db.get(AiChat, chat_id)
        db.refresh(chat)
        assert chat.title == "First question"  # title from the opening question
        msgs = (
            db.query(AiChatMessage)
            .filter(AiChatMessage.chat_id == chat_id)
            .order_by(AiChatMessage.id.asc())
            .all()
        )
        assert [m.content for m in msgs] == [
            "First question", "**Answer**", "Second question", "**Answer**",
        ]

    def test_two_chats_do_not_mix(
        self, client, user, pcap_session, mock_adapter, monkeypatch, db
    ):
        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        r1 = _ask(client, pcap_session[0].id, token, question="Chat one question")
        r2 = _ask(client, pcap_session[0].id, token, question="Chat two question")
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["chat_id"] != r2.json()["chat_id"]

        for r, q in ((r1, "Chat one question"), (r2, "Chat two question")):
            msgs = (
                db.query(AiChatMessage)
                .filter(AiChatMessage.chat_id == r.json()["chat_id"])
                .order_by(AiChatMessage.id.asc())
                .all()
            )
            assert [m.content for m in msgs] == [q, "**Answer**"]
        assert (
            db.query(AiChatMessage)
            .filter(AiChatMessage.session_id == pcap_session[0].id)
            .count()
            == 4
        )

    def test_foreign_chat_403(self, client, user, pcap_session, mock_adapter, monkeypatch, db):
        _, token = user
        other, _ = _other_user(db)
        foreign = AiChat(user_id=other.id, session_id=pcap_session[0].id, title="t")
        db.add(foreign)
        db.commit()

        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        resp = _ask(
            client, pcap_session[0].id, token, question="hi", chat_id=foreign.id
        )
        assert resp.status_code == 403

    def test_unknown_chat_404(self, client, user, pcap_session, mock_adapter, monkeypatch):
        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        resp = _ask(
            client, pcap_session[0].id, token, question="hi", chat_id="nope"
        )
        assert resp.status_code == 404

    def test_chat_of_other_session_404(
        self, client, user, pcap_session, mock_adapter, monkeypatch, db
    ):
        from src.db.models import Session as SessionModel

        _, token = user
        other_session = SessionModel(
            id="other-session-x",
            user_id=user[0].id,
            filename="x.pcapng",
            pcap_path="nonexistent.pcapng",
            topology_json_path="",
        )
        db.add(other_session)
        chat = AiChat(user_id=user[0].id, session_id=other_session.id, title="t")
        db.add(chat)
        db.commit()

        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        resp = _ask(
            client, pcap_session[0].id, token, question="hi", chat_id=chat.id
        )
        assert resp.status_code == 404


class TestChatsList:
    def _make_chat(self, db, user_id, session_id, title, created_at):
        chat = AiChat(
            user_id=user_id, session_id=session_id, title=title,
            created_at=created_at,
        )
        db.add(chat)
        db.flush()
        return chat

    def test_user_scoped_across_sessions_with_tokens(
        self, client, user, pcap_session, db
    ):
        _, token = user
        sid = pcap_session[0].id
        other_session = SessionModel(
            id="other-session-list",
            user_id=user[0].id,
            filename="other.pcapng",
            pcap_path="nonexistent.pcapng",
            topology_json_path="",
        )
        db.add(other_session)

        old = self._make_chat(
            db, user[0].id, sid, "old",
            datetime.now(UTC) - timedelta(minutes=5),
        )
        new = self._make_chat(
            db, user[0].id, other_session.id, "new", datetime.now(UTC),
        )
        db.add_all(
            [
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, chat_id=old.id,
                    role="user", content="q1", created_at=datetime.now(UTC),
                ),
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, chat_id=old.id,
                    role="assistant", content="a1", created_at=datetime.now(UTC),
                ),
                AiChatMessage(
                    user_id=user[0].id, session_id=other_session.id, chat_id=new.id,
                    role="user", content="q2", created_at=datetime.now(UTC),
                ),
            ]
        )
        # Two usage rows for "old" (60 tokens total), none for "new".
        db.add_all(
            [
                AiUsage(user_id=user[0].id, tokens=40, chat_id=old.id),
                AiUsage(user_id=user[0].id, tokens=20, chat_id=old.id),
            ]
        )
        db.commit()

        resp = client.get("/api/ai/chats", cookies=auth_cookie(token))
        assert resp.status_code == 200
        chats = resp.json()["chats"]
        assert [c["id"] for c in chats] == [new.id, old.id]  # newest first
        assert [c["title"] for c in chats] == ["new", "old"]
        assert [c["message_count"] for c in chats] == [1, 2]
        assert [c["tokens"] for c in chats] == [0, 60]  # summed per chat
        assert [c["session_filename"] for c in chats] == ["other.pcapng", "test_drop.pcapng"]
        assert all(c["created_at"] for c in chats)

    def test_empty(self, client, user):
        _, token = user
        resp = client.get("/api/ai/chats", cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert resp.json() == {"chats": []}

    def test_other_users_chats_excluded(self, client, user, pcap_session, db):
        other, other_token = _other_user(db)
        db.add(AiChat(user_id=other.id, session_id=pcap_session[0].id, title="theirs"))
        db.add(AiChat(user_id=user[0].id, session_id=pcap_session[0].id, title="mine"))
        db.commit()

        resp = client.get("/api/ai/chats", cookies=auth_cookie(user[1]))
        assert resp.status_code == 200
        chats = resp.json()["chats"]
        assert [c["title"] for c in chats] == ["mine"]

        resp = client.get("/api/ai/chats", cookies=auth_cookie(other_token))
        assert [c["title"] for c in resp.json()["chats"]] == ["theirs"]

    def test_unauthenticated_401(self, client):
        assert client.get("/api/ai/chats").status_code == 401


class TestRemovedChatRoutes:
    def test_load_messages_endpoint_gone(self, client, user, pcap_session, db):
        """GET /api/ai/chats/{id} was removed; DELETE on the same path remains."""
        chat = AiChat(user_id=user[0].id, session_id=pcap_session[0].id, title="t")
        db.add(chat)
        db.commit()
        resp = client.get(f"/api/ai/chats/{chat.id}", cookies=auth_cookie(user[1]))
        assert resp.status_code == 405  # path matches DELETE only

    def test_session_scoped_list_gone(self, client, user, pcap_session):
        resp = client.get(
            f"/api/sessions/{pcap_session[0].id}/chats", cookies=auth_cookie(user[1])
        )
        assert resp.status_code == 404


class TestDeleteChat:
    def test_deletes_chat_and_messages(self, client, user, pcap_session, db):
        _, token = user
        sid = pcap_session[0].id
        chat = AiChat(user_id=user[0].id, session_id=sid, title="t")
        db.add(chat)
        db.flush()
        db.add(
            AiChatMessage(
                user_id=user[0].id, session_id=sid, chat_id=chat.id,
                role="user", content="q", created_at=datetime.now(UTC),
            )
        )
        db.commit()

        resp = client.delete(f"/api/ai/chats/{chat.id}", cookies=auth_cookie(token))
        assert resp.status_code == 204
        assert db.query(AiChatMessage).filter(AiChatMessage.chat_id == chat.id).count() == 0
        assert db.query(AiChat).filter(AiChat.id == chat.id).count() == 0
        assert (
            client.get(
                f"/api/ai/chats/{chat.id}/export", cookies=auth_cookie(token)
            ).status_code
            == 404
        )

    def test_owner_scoped_403(self, client, user, pcap_session, db):
        token = _other_user(db)[1]
        chat = AiChat(user_id=user[0].id, session_id=pcap_session[0].id, title="t")
        db.add(chat)
        db.commit()
        resp = client.delete(f"/api/ai/chats/{chat.id}", cookies=auth_cookie(token))
        assert resp.status_code == 403
        assert db.query(AiChat).filter(AiChat.id == chat.id).count() == 1

    def test_unauthenticated_401(self, client, user, pcap_session, db):
        chat = AiChat(user_id=user[0].id, session_id=pcap_session[0].id, title="t")
        db.add(chat)
        db.commit()
        assert client.delete(f"/api/ai/chats/{chat.id}").status_code == 401


class TestExportChat:
    def test_headers_and_format_with_title(self, client, user, pcap_session, db):
        _, token = user
        sid = pcap_session[0].id
        chat = AiChat(user_id=user[0].id, session_id=sid, title="Host questions")
        db.add(chat)
        db.flush()
        db.add_all(
            [
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, chat_id=chat.id,
                    role="user", content="What hosts are present?",
                    created_at=datetime(2026, 11, 13, 14, 5, tzinfo=UTC),
                ),
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, chat_id=chat.id,
                    role="assistant", content="**Answer**",
                    created_at=datetime(2026, 11, 13, 14, 6, tzinfo=UTC),
                ),
            ]
        )
        db.commit()

        resp = client.get(f"/api/ai/chats/{chat.id}/export", cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
        assert resp.headers["content-disposition"] == (
            f'attachment; filename="netvisor-chat-{chat.id}.md"'
        )
        body = resp.text
        assert body.startswith("# Host questions\n")
        assert "**[user, 14:05]**\n\nWhat hosts are present?" in body
        assert "**[assistant, 14:06]**\n\n**Answer**" in body

    def test_h1_fallback_when_title_null(self, client, user, pcap_session, db):
        _, token = user
        chat = AiChat(
            user_id=user[0].id, session_id=pcap_session[0].id, title=None
        )
        db.add(chat)
        db.commit()
        resp = client.get(f"/api/ai/chats/{chat.id}/export", cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert resp.text.startswith("# NetVisor chat\n")

    def test_owner_scoped_403(self, client, user, pcap_session, db):
        token = _other_user(db)[1]
        chat = AiChat(user_id=user[0].id, session_id=pcap_session[0].id, title="t")
        db.add(chat)
        db.commit()
        resp = client.get(f"/api/ai/chats/{chat.id}/export", cookies=auth_cookie(token))
        assert resp.status_code == 403

    def test_unauthenticated_401(self, client, user, pcap_session, db):
        chat = AiChat(user_id=user[0].id, session_id=pcap_session[0].id, title="t")
        db.add(chat)
        db.commit()
        assert client.get(f"/api/ai/chats/{chat.id}/export").status_code == 401


class TestSessionDeleteCascadesChats:
    def test_deleting_session_removes_chats_and_messages(self, client, user, pcap_session, db):
        _, token = user
        sid = pcap_session[0].id
        chat = AiChat(user_id=user[0].id, session_id=sid, title="t")
        db.add(chat)
        db.flush()
        db.add_all(
            [
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, chat_id=chat.id,
                    role="user", content="q", created_at=datetime.now(UTC),
                ),
                AiChatMessage(
                    user_id=user[0].id, session_id=sid, chat_id=chat.id,
                    role="assistant", content="a", created_at=datetime.now(UTC),
                ),
            ]
        )
        db.commit()

        resp = client.delete(f"/api/sessions/{sid}", cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert db.query(AiChatMessage).filter(AiChatMessage.session_id == sid).count() == 0
        assert db.query(AiChat).filter(AiChat.session_id == sid).count() == 0
