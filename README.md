# DoDomuDojadę v2

Wirtualna tablica informacyjna szkoły: ekran z odjazdami autobusów i tramwajów, pogodą, ogłoszeniami, odliczaniem, wydarzeniami z kalendarza, cytatem i słowem dnia oraz panel administracyjny do zarządzania treścią.

To druga wersja projektu, przepisana z PHP na Pythona. Pierwsza wersja i plan migracji: [SLOths4/DoDomuDojade](https://github.com/SLOths4/DoDomuDojade) (`resources/docs/python-migration.md`).

> **Stan:** etap 0 (fundamenty). Działa szkielet: baza ze schematem, API z obsługą błędów, CLI, frontend i Docker. Funkcje ekranu i panelu powstają w kolejnych etapach.

## Uruchomienie

Wymagany jest Docker z Docker Compose.

```bash
cp .env.example .env    # uzupełnij hasło bazy, SECRET_KEY i klucze API
./ddd up
./ddd user add admin
```

Aplikacja działa pod `http://localhost/` (port zmienisz w `HTTP_PORT`):

| Adres | Co to jest |
|---|---|
| `/display/` | ekran (otwierany przez Firefoksa na Raspberry Pi) |
| `/panel/` | panel administracyjny |
| `/api/docs` | dokumentacja API |
| `/api/health` | stan aplikacji |

Migracje bazy uruchamiają się same przy starcie kontenera `api`.

Plik konta serwisowego Google wrzuć do katalogu `secrets/` jako `google-service-account.json`.

## Polecenia `ddd`

| Polecenie | Działanie |
|---|---|
| `./ddd up` / `./ddd down` / `./ddd restart` | start, zatrzymanie, restart |
| `./ddd logs [api\|web\|db]` | logi |
| `./ddd ps` | stan kontenerów |
| `./ddd migrate` | aktualizacja schematu bazy |
| `./ddd user add <login> [--role admin\|moderator]` | nowy użytkownik; hasło jest pytane interaktywnie |
| `./ddd backup` | zrzut bazy do `backups/` |

## Struktura

```
backend/            API: Python 3.13, FastAPI, SQLAlchemy 2, Alembic
  app/core/         konfiguracja, baza, błędy, tłumaczenia, hasła
  app/<moduł>/      jeden katalog na funkcję (models.py, a później schemas.py, service.py, router.py)
  alembic/          migracje bazy
frontend/           strony HTML + Alpine.js + Tailwind CSS, serwowane przez Caddy
  display/          ekran
  panel/            panel administracyjny
  shared/           klient API, tłumaczenia (pl, en), style
docker-compose.yml  db (PostgreSQL 17), api, web (Caddy)
ddd                 skrypt z poleceniami
```

## Rozwój

Backend (wymaga [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run pytest
```

Testy oznaczone `db` potrzebują PostgreSQL wskazanego w `TEST_DATABASE_URL`, np.:

```bash
docker run -d --rm --name ddd-test-db -e POSTGRES_USER=ddd -e POSTGRES_PASSWORD=ddd -e POSTGRES_DB=dodomudojade -p 55432:5432 postgres:17-alpine
TEST_DATABASE_URL=postgresql+psycopg://ddd:ddd@localhost:55432/dodomudojade uv run pytest
```

Nowa migracja po zmianie modeli: `uv run alembic revision --autogenerate -m "opis"`.

Frontend:

```bash
cd frontend
npm ci
npm run build   # wynik w frontend/dist
```

CI (GitHub Actions) uruchamia lint, typy i testy backendu, build frontendu oraz build obrazów Dockera.

## Licencja

[CC BY-NC 4.0](LICENSE) © SLOths4
