---
title: Network, storage and security API
description: HTTPS, WebSocket, SQLite, storage, crypto and authentication reference.
---

# Network, storage and security API

| Object | Methods |
| --- | --- |
| `https` | `get`, `post`, `put`, `patch`, `delete` |
| `websocket` | `connect`, `send`, `close`, `is_connected`, `close_all` |
| `storage` | `set`, `get`, `delete`, `clear`, `keys` |
| `crypto` | `hash_password`, `verify_password`, `encrypt`, `decrypt` |
| `db` | `execute`, `query`, `last_insert_id`, `begin`, `commit`, `rollback` |
| `auth` | `login`, `user`, `token`, `is_logged_in`, `logout` |
| `json_get` | read a safe dotted path from JSON text |

HTTP callbacks are named `on_response`; WebSocket callbacks separate open,
message, close and error events.

Start with [SQLite and protected local data](../guides/sqlite-security.md),
[Real-time WebSocket chat](../guides/chat-realtime.md) and
[Data, network and security](../data-security.md).
