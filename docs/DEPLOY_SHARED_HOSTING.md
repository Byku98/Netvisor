# Deploying NetVisor to SEOHost.pl (shared hosting, Passenger)

Manual deployment guide — Target A from `netvisor-backend/docs/TODO.md` P11.
Verified working layout: Passenger (Python 3.13) → FastAPI via WSGI bridge →
serves both `/api/*` and the built frontend from one domain.

## Prerequisites (one-time)

- SEOHost.pl plan with SSH + "Aplikacje internetowe" (Node.js/Python apps UI)
- Domain pointed at the hosting (e.g. `tomaszbyczek.pl`)
- Deploy artifact: `netvisor-deploy.tar.gz` (built locally: backend src + frontend dist)

## 1. Create the app in DirectAdmin

Panel → **Aplikacje internetowe → Utwórz aplikację** (Python) — ACTUAL layout used:

| Field | Value |
|---|---|
| Wersja Python | **3.13.15 (zalecane)** |
| Katalog główny aplikacji | `/domains/netvisor.tomaszbyczek.pl/backend` |
| URL aplikacji | `netvisor.tomaszbyczek.pl` + path `/backend` |
| Plik startowy aplikacji | `passenger_wsgi.py` |
| Punkt wejścia aplikacji | `application` |

Architecture: LiteSpeed serves the built frontend from
`/domains/netvisor.tomaszbyczek.pl/public_html` at the domain root; the Python
app handles `/backend/*`. Frontend is built with `VITE_API_URL=/backend/api`.

## 2. Upload and extract

```bash
# From your PC (repo root):
scp netvisor-deploy.tar.gz srv94329@h65.seohost.pl:~/

# On the server:
ssh srv94329@h65.seohost.pl
tar -xzf netvisor-deploy.tar.gz -C ~/tmp-deploy    # staging dir
cp -r ~/tmp-deploy/netvisor-backend/src ~/tmp-deploy/netvisor-backend/passenger_wsgi.py \
      ~/tmp-deploy/netvisor-backend/requirements.txt \
      /domains/netvisor.tomaszbyczek.pl/backend/
cp -r ~/tmp-deploy/netvisor-frontend/dist/* /domains/netvisor.tomaszbyczek.pl/public_html/
```

(FTP via DirectAdmin File Manager works too.)

## 3. Install dependencies into the app venv

```bash
source ~/virtualenv/<app-venv-path>/3.13/bin/activate   # path shown in panel
pip install --upgrade pip
pip install -r /domains/netvisor.tomaszbyczek.pl/backend/requirements.txt
```

## 4. Environment variables (panel UI)

| Name | Value |
|---|---|
| `NETVISOR_JWT_SECRET` | `openssl rand -hex 32` (run over SSH, paste output) |

Optional later: `NETVISOR_GOOGLE_CLIENT_ID` (OAuth for the domain).

## 5. Restart and test

Panel → **Restart** (or `mkdir -p /domains/netvisor.tomaszbyczek.pl/backend/tmp && touch /domains/netvisor.tomaszbyczek.pl/backend/tmp/restart.txt`).

```bash
# ⚠️ Passenger sub-URI check — first thing to verify:
curl -i https://netvisor.tomaszbyczek.pl/backend/health
# expect {"status":"ok"}; if 404 → Passenger didn't strip the /backend prefix
# (PATH_INFO vs SCRIPT_NAME) — fix: strip prefix in passenger_wsgi.py

curl https://netvisor.tomaszbyczek.pl/backend/api/sessions   # []
curl -I https://netvisor.tomaszbyczek.pl/                    # frontend index.html (LiteSpeed)
```

Then open `https://netvisor.tomaszbyczek.pl` — upload `test_drop.pcapng`.

## Known limitations on shared hosting (first deploy)

- **No tshark** → packet table, dissection, filters, Follow TCP Stream return 503.
  Graph, upload, stats, sessions, auth all work. Fix = Scapy fallback (TODO P11.5).
- **Upload size** — Passenger/LiteSpeed may cap request bodies; test with the small
  `test_drop.pcapng` first, then try bigger files to find the ceiling.
- **Logs** — `~/netvisor/logs/netvisor.log` (writable home dir, fine).

## Rollback

Keep the previous tarball; re-extract over the app dir and restart. The SQLite DB
and PCAPs live in `~/netvisor/data/` — they survive redeploys (tarball has no data/).
