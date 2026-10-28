# DoDomuDojadę v2

Wirtualna tablica informacyjna szkoły: ekran z odjazdami autobusów i tramwajów, pogodą, ogłoszeniami, odliczaniem, wydarzeniami z kalendarza, cytatem i słowem dnia oraz panel administracyjny do zarządzania treścią.

To druga wersja projektu, przepisana z PHP na Pythona. Pierwsza wersja i plan migracji: [SLOths4/DoDomuDojade](https://github.com/SLOths4/DoDomuDojade) (`resources/docs/python-migration.md`).

> **Stan:** etapy 1–3 backendu. Działa API panelu i ekranu, integracje i strumień SSE. Frontend ekranu i panelu powstaje w kolejnych etapach.

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
| `./ddd fetch` | natychmiast pobiera rozkład, pogodę, kalendarz oraz cytat i słowo dnia (normalnie robi to harmonogram) |
| `./ddd cleanup` | usuwa odrzucone ogłoszenia i wpisy dziennika zdarzeń starsze niż 30 dni (robi to też harmonogram codziennie o 3:30) |
| `./ddd backup` | zrzut bazy do `backups/` |

## API

Pełna, klikalna dokumentacja: `/api/docs`. JSON używa `camelCase`.

| Grupa | Endpointy | Dostęp |
|---|---|---|
| Logowanie | `POST /api/auth/login`, `POST /api/auth/logout`, `GET`/`PATCH /api/auth/me` (język), `POST /api/auth/password` | publiczne / zalogowani |
| Użytkownicy | `GET`/`POST /api/users`, `PATCH`/`DELETE /api/users/{id}`, `POST /api/users/{id}/password` | admin |
| Ogłoszenia | `GET`/`POST /api/announcements` (`?status=pending\|approved\|rejected`), `GET`/`PATCH`/`DELETE /api/announcements/{id}`, `POST …/{id}/approve`, `POST …/{id}/reject` | moderator, admin |
| Propozycje | `POST /api/announcements/proposals` (limit 5 na godzinę z jednego adresu) | publiczne |
| Odliczania | `GET`/`POST /api/countdowns`, `GET`/`PATCH`/`DELETE /api/countdowns/{id}` | moderator, admin |
| Moduły ekranu | `GET /api/modules` (moderator, admin), `PATCH /api/modules/{id}` (admin) | |
| Ekran | `GET /api/display` (wszystkie moduły), `GET /api/display/{moduł}`, `GET /api/display/stream` (SSE) | publiczne |
| Pomocnicze | `GET /api/config` (limity pól dla formularzy), `GET /api/health`, `GET /api/health/db` | publiczne |

Zasady:

- Sesja w podpisanym ciasteczku `ddd_session`. Żądania zmieniające dane muszą mieć nagłówek `X-CSRF-Token` z wartością ciasteczka `csrf_token` (ustawianego przy każdej odpowiedzi API).
- Niezalogowany dostaje `401`, brak uprawnień `403`. Konto z wymuszoną zmianą hasła (`mustChangePassword`) może tylko zmienić hasło, wylogować się i odczytać `/api/auth/me`.
- Konto utworzone lub z hasłem zresetowanym przez admina musi zmienić hasło przy pierwszym logowaniu. Zmiana hasła i dezaktywacja wylogowują wszystkie inne sesje.
- 5 nieudanych logowań z jednego adresu na ten sam login blokuje logowanie na 15 minut.
- Błędy mają postać `{"status": "error", "data": {"code", "context"}, "message", "request_id"}`; komunikat w języku z `Accept-Language` (pl lub en). Błędy walidacji to `400` z `context.fields`.
- Ogłoszenie dodane w panelu jest od razu zatwierdzone; propozycja publiczna czeka na zatwierdzenie (domyślna ważność 30 dni). Data ważności: od dziś do roku naprzód, sprawdzana tylko przy zmianie. Status zmieniają wyłącznie `approve` i `reject`.
- Okno modułu: `startTime` = `endTime` oznacza cały dzień, `startTime` > `endTime` — okno przez północ.
- Każda zmiana ogłoszeń, odliczań i modułów trafia do tabeli `events` w tej samej transakcji (pod ekran na żywo).

## Dane ekranu

| Moduł | Źródło | Odświeżanie |
|---|---|---|
| `departures` | ZTM Poznań: rozkład GTFS (raz dziennie o 3:00) + opóźnienia GTFS-RT; wszystkie słupki o nazwie `STOP_NAME` (domyślnie AWF), autobusy i tramwaje, 90 minut naprzód | co 30 s |
| `weather` | IMGW (temperatura, ciśnienie) + Airly (jakość powietrza, gdy jest klucz) | co 15 min |
| `calendar` | Google Calendar przez konto serwisowe | co 5 min |
| `quote`, `word` | Wikicytaty i Wikisłownik albo Wikiquote i Wiktionary — dzień po polsku, dzień po angielsku; przy braku sieci lokalna lista | raz dziennie (i przy starcie) |
| `announcement`, `countdown` | baza | przy każdej zmianie |

Każdy moduł zwraca `{"status": "active"|"empty"|"inactive", "data", "message"}`. `inactive` — moduł wyłączony lub poza swoim oknem czasowym.

Strumień `GET /api/display/stream` (SSE) wysyła `event: snapshot` z wszystkimi modułami po połączeniu i co minutę, a `event: module` (`{"name", "status", "data", "message"}`) gdy zmieni się pojedynczy moduł. Ostatnie wyniki pogody i kalendarza są trzymane w bazie, więc po restarcie ekran od razu ma dane.

Dane ZTM: źródło ZTM Poznań (otwarte dane), przetworzone. Cytaty i słowa z projektów Wikimedia na licencji CC BY-SA — ekran podaje źródło.

## Struktura

```
backend/            API: Python 3.13, FastAPI, SQLAlchemy 2, Alembic
  app/core/         konfiguracja, baza, sesja i CSRF, błędy, tłumaczenia, zdarzenia, harmonogram
  app/<moduł>/      jeden katalog na funkcję: models.py, schemas.py, service.py, router.py
  app/integrations/ ZTM (GTFS), pogoda, kalendarz, cytat i słowo dnia
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
