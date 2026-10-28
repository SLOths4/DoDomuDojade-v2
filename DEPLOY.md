# Wdrożenie na serwer szkolny

Instrukcja dla osoby, która utrzymuje serwer (uczniowie, informatyk). Zakłada serwer z Linuksem w sieci szkolnej i ekran na Raspberry Pi z Firefoksem.

## 1. Przygotowanie serwera (raz)

1. Zainstaluj Docker Engine z wtyczką Compose: <https://docs.docker.com/engine/install/>. Sprawdź:
   ```bash
   docker compose version
   ```
2. Włącz uruchamianie Dockera przy starcie systemu (kontenery mają `restart: unless-stopped`, więc wstaną same po restarcie serwera):
   ```bash
   sudo systemctl enable --now docker
   ```
3. Pobierz kod:
   ```bash
   git clone https://github.com/SLOths4/DoDomuDojade-v2.git
   cd DoDomuDojade-v2
   ```

## 2. Konfiguracja

```bash
cp .env.example .env
```

W `.env` ustaw co najmniej:

| Zmienna | Co wpisać |
|---|---|
| `POSTGRES_PASSWORD` | długie losowe hasło (np. `openssl rand -hex 24`) |
| `SECRET_KEY` | losowy ciąg (np. `openssl rand -hex 32`); zmiana wylogowuje wszystkich |
| `HTTP_PORT` | `80`, chyba że port jest zajęty |
| `AIRLY_API_KEY`, `AIRLY_LOCATION_ID` | z obecnego serwera (plik `.env` wersji PHP) |
| `GOOGLE_CALENDAR_ID` | z obecnego serwera (`CALENDAR_ID`) |

Plik konta serwisowego Google (w wersji PHP wskazywany przez `CALENDAR_API_KEY_PATH`) skopiuj do `secrets/google-service-account.json`, np. z obecnego serwera:

```bash
scp uzytkownik@stary-serwer:/sciezka/do/klucza.json secrets/google-service-account.json
```

Bez kluczy Airly i Google aplikacja działa — ekran pokaże pogodę bez jakości powietrza i pusty kalendarz.

## 3. Uruchomienie

```bash
./ddd up
./ddd user add admin --role admin
```

Sprawdź:

- `http://<adres-serwera>/api/health/db` → `{"status":"ok"}`
- `http://<adres-serwera>/display/` → ekran z odjazdami (rozkład ZTM pobiera się ok. 30 s po starcie)
- `http://<adres-serwera>/panel/` → logowanie

Dodaj konta nauczycieli w panelu (Użytkownicy → Nowy użytkownik). Każdy zmieni hasło startowe przy pierwszym logowaniu.

## 4. Ekran (Raspberry Pi)

Raspberry Pi jest tylko klientem: otwiera stronę ekranu w Firefoksie. Zmień adres, który otwiera, na:

```
http://<adres-serwera>/display/
```

Jeśli Firefox jest uruchamiany z terminala, tryb pełnoekranowy bez interfejsu to:

```bash
firefox --kiosk http://<adres-serwera>/display/
```

Ekran sam odświeża dane (SSE). Po zerwaniu połączenia łączy się ponownie, po 30 s przechodzi na odpytywanie, a po 10 minutach bez serwera przeładowuje stronę — nie trzeba go ręcznie odświeżać po restarcie serwera.

## 5. Przełączenie ze starej wersji

1. Uruchom nową wersję obok starej (inny serwer albo inny port: `HTTP_PORT=8080`).
2. Przenieś klucze (krok 2), utwórz konta (krok 3).
3. Otwórz `/display/` na komputerze i porównaj ze starym ekranem: odjazdy, pogoda, kalendarz, cytat i słowo.
4. Przełącz adres na Raspberry Pi (krok 4).
5. Obserwuj ekran przez kilka dni. Stary serwer zostaw włączony — powrót to zmiana adresu na Raspberry Pi z powrotem.
6. Gdy wszystko działa: wyłącz starą wersję, przemianuj repozytorium `SLOths4/DoDomuDojade` na `DoDomuDojade-php` i zarchiwizuj je.

Danych ze starej bazy nie przenosimy — ogłoszenia i odliczania wprowadza się od nowa.

## Codzienna obsługa

| Zadanie | Polecenie |
|---|---|
| Aktualizacja do najnowszej wersji z GitHuba | `./ddd update` |
| Logi | `./ddd logs api` (wyjście: Ctrl+C) |
| Stan kontenerów | `./ddd ps` |
| Kopia bazy | `./ddd backup` (plik w `backups/`) |
| Przywrócenie kopii | `docker compose exec -T db psql -U ddd -d dodomudojade < backups/plik.sql` (na pustej bazie) |
| Natychmiastowe pobranie danych ekranu | `./ddd fetch` |
| Nowy administrator z wiersza poleceń | `./ddd user add <login> --role admin` |

Zadania cykliczne (rozkład, opóźnienia, pogoda, kalendarz, cytat i słowo dnia, sprzątanie) działają w aplikacji — nie trzeba konfigurować crona.

## Rozwiązywanie problemów

| Objaw | Co sprawdzić |
|---|---|
| Ekran pokazuje „Ponowne łączenie…” | `./ddd ps` — czy `api` ma stan `healthy`; `./ddd logs api` |
| Brak odjazdów | `./ddd logs api` — błędy pobierania z ZTM; czy serwer ma dostęp do internetu; `./ddd fetch` |
| Brak pogody | `IMGW_WEATHER_URL` w `.env` |
| Pusty kalendarz | `GOOGLE_CALENDAR_ID`, plik w `secrets/`, czy kalendarz jest udostępniony kontu serwisowemu |
| „Sesja formularza wygasła” w panelu | odśwież stronę |
| Nikt nie może się zalogować | `./ddd user add <login> --role admin` tworzy nowe konto administratora |

## Później: logowanie Google

Logowanie kontem szkolnym Google wymaga domeny z publiczną końcówką (np. `ekran.szkola.pl`), która w sieci szkolnej wskazuje na serwer, oraz HTTPS. Serwer nie musi być dostępny z internetu. Wtedy ustaw też `COOKIE_SECURE=true`.
