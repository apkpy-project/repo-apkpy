"""Remote push notifications with a deterministic desktop simulation.

Android builds use Firebase Cloud Messaging.  The Previewer cannot register
with FCM, so it exposes the same callbacks through :meth:`PushAPI.simulate` and
renders the same notification banner used by ``notify()``.
"""

from __future__ import annotations

import json
import re
import threading
import uuid


_TOPIC_RE = re.compile(r"^[A-Za-z0-9_.~%\-]{1,900}$")


class PushAPI:
    """Small FCM-compatible API shared by Previewer and generated Android.

    ``listen`` installs one app-level listener.  Repeating it replaces the
    previous callbacks, which avoids duplicate delivery after hot reloads.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._on_message = None
        self._on_token = None
        self._on_error = None
        self._auto_notify = True
        self._channel_id = "apkpy_push"
        self._channel_name = "Updates"
        self._topics = set()
        self._token = "preview-" + uuid.uuid4().hex

    @staticmethod
    def _deliver(callback, *args):
        if callback is None:
            return
        root = None
        try:
            from .. import ui

            instance = getattr(ui._app, "_instance", None)
            root = getattr(instance, "root", None)
        except Exception:
            root = None
        if root is not None:
            try:
                root.after(0, lambda: callback(*args))
                return
            except Exception:
                pass
        callback(*args)

    @staticmethod
    def _data_json(data):
        if data is None:
            return "{}"
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                return json.dumps({"value": data}, ensure_ascii=False, separators=(",", ":"))
        if isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return json.dumps({"value": str(data)}, ensure_ascii=False, separators=(",", ":"))

    def listen(
        self,
        screen=None,
        on_message=None,
        on_token=None,
        on_error=None,
        auto_notify=True,
        channel_id="apkpy_push",
        channel_name="Updates",
    ):
        """Listen for push messages.

        ``screen`` scopes the generated Android receiver to one Activity.  It
        is intentionally ignored by the Previewer, where there is one window.
        """
        del screen
        with self._lock:
            self._on_message = on_message
            self._on_token = on_token
            self._on_error = on_error
            self._auto_notify = bool(auto_notify)
            self._channel_id, self._channel_name = str(channel_id), str(channel_name)
            token = self._token
        self._deliver(on_token, token)
        return token

    def get_token(self, on_result=None):
        """Return the current registration token asynchronously."""
        with self._lock:
            token = self._token
        self._deliver(on_result, True, token)
        return token

    def subscribe(self, topic, on_result=None):
        """Subscribe to an FCM topic, validating the same topic alphabet."""
        clean = str(topic or "").strip()
        if not _TOPIC_RE.fullmatch(clean):
            message = "Invalid topic: use letters, numbers, _ . - ~ or %"
            self._deliver(on_result, False, message)
            with self._lock:
                error = self._on_error
            self._deliver(error, message)
            return False
        with self._lock:
            self._topics.add(clean)
        self._deliver(on_result, True, clean)
        return True

    def unsubscribe(self, topic, on_result=None):
        """Remove a topic subscription."""
        clean = str(topic or "").strip()
        with self._lock:
            self._topics.discard(clean)
        self._deliver(on_result, True, clean)
        return True

    def simulate(self, title, body, data=None):
        """Deliver a push locally, including an Android-style notification."""
        clean_title = str(title or "Update")
        clean_body = str(body or "")
        data_json = self._data_json(data)
        with self._lock:
            callback = self._on_message
            auto_notify = self._auto_notify
        # Deliver first.  Besides making the state update feel immediate, this
        # keeps headless Preview tests deterministic without creating a Tk root.
        self._deliver(callback, clean_title, clean_body, data_json)
        if auto_notify:
            try:
                from ..ui import notify
                from .notifications import notifications
                notifications.channel(self._channel_id, self._channel_name)
                notify(clean_title, clean_body, id="push_"+uuid.uuid4().hex,
                       channel=self._channel_id, style="big_text")
            except Exception:
                pass
        return data_json

    def reset(self):
        """Clear Previewer callbacks and topic state (mainly for tests)."""
        with self._lock:
            self._on_message = None
            self._on_token = None
            self._on_error = None
            self._auto_notify = True
            self._topics.clear()


push = PushAPI()

__all__ = ["PushAPI", "push"]
