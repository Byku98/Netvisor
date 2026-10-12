# Deploying NetVisor to SEOHost.pl (shared hosting, Passenger)

Manual deployment guide — Target A from `netvisor-backend/docs/TODO.md` P11.
Verified working layout: Passenger (Python 3.13) → FastAPI via WSGI bridge →
serves both `/api/*` and the built frontend from one domain.

## Prerequisites (one-time)

- SEOHost.pl plan with SSH + "Aplikacje internetowe" (Node.js/Python apps UI)
- Domain pointed at the hosting (e.g. `tomaszbyczek.pl`)
- Deploy artifact: `netvisor-deploy.tar.gz` (built locally: backend src + frontend dist)

## 1. Create the app in DirectAdmin

Panel → **Aplikacje internetowe → Utwórz aplikację** (Python):

| Field | Value |
|---|---|
| Wersja Python | **3.13.15 (zalecane)** |
| Katalog główny aplikacji | `/home/srv94329/netvisor` |
| URL aplikacji | `tomaszbyczek.pl` (root) — or a subpath like `/netvisor` if you want it separate |
| Plik startowy aplikacji | `passenger_wsgi.py` |
| Punkt wejścia aplikacji | `application` |

NOTE: the panel creates the app first with a placeholder startup file — create it,
upload our files, then fix the two startup fields and restart.

## 2. Upload and extract

```bash
# From your PC (repo root) — scp is faster than FTP since SSH works:
scp netvisor-deploy.tar.gz srv94329@h65.seohost.pl:~/

# On the server:
ssh srv94329@h65.seohost.pl
mkdir -p ~/netvisor
tar -xzf netvisor-deploy.tar.gz -C ~/netvisor --strip-components=1
ls ~/netvisor
# expect: passenger_wsgi.py  requirements.txt  pyproject.toml  src/  netvisor-frontend/
```

(FTP works too — DirectAdmin → File Manager → upload → extract.)

## 3. Install dependencies into the app venv

The panel creates a virtualenv for the app (path shown in the panel, usually
`~/virtualenv/<app>/<version>/`). Over SSH:

```bash
source ~/virtualenv/netvisor/3.13/bin/activate   # adjust to the panel-shown path
pip install --upgrade pip
pip install -r ~/netvisor/requirements.txt
```

## 4. Environment variables (panel UI)

In the app's **Environment variables** section add:

| Name | Value |
|---|---|
| `NETVISOR_STATIC_DIR` | `/home/srv94329/netvisor/netvisor-frontend/dist` |
| `NETVISOR_JWT_SECRET` | long random string (`openssl rand -hex 32`) |
| `NETVISOR_CORS_ORIGINS` | `["https://tomaszbyczek.pl"]` (optional; same-origin needs none) |

Then set the startup fields:
- **Plik startowy:** `passenger_wsgi.py`
- **Punkt wejścia:** `application`

## 5. Restart and test

Panel → **Restart** (or `touch ~/netvisor/passenger_wsgi.py` / `mkdir ~/netvisor/tmp && touch ~/netvisor/tmp/restart.txt`).

```bash
curl https://tomaszbyczek.pl/health        # {"status":"ok"}
curl https://tomaszbyczek.pl/api/sessions  # []
```

Then open `https://tomaszbyczek.pl` — the NetVisor UI should load.
Log in with username/password (Google OAuth needs a redirect URI update — later step).

## Known limitations on shared hosting (first deploy)

- **No tshark** → packet table, dissection, filters, Follow TCP Stream return 503.
  Graph, upload, stats, sessions, auth all work. Fix = Scapy fallback (TODO P11.5).
- **Upload size** — Passenger/LiteSpeed may cap request bodies; test with the small
  `test_drop.pcapng` first, then try bigger files to find the ceiling.
- **Logs** — `~/netvisor/logs/netvisor.log` (writable home dir, fine).

## Rollback

Keep the previous tarball; re-extract over the app dir and restart. The SQLite DB
and PCAPs live in `~/netvisor/data/` — they survive redeploys (tarball has no data/).
