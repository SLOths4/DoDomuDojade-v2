# AGENTS.md

Instrukcje dla agentów AI pracujących w repozytorium **DoDomuDojade-v2**.

## Zasady
- Projekt ma być prosty do uruchomienia i utrzymania przez uczniów: bez zbędnych warstw, frameworków i zależności.
- Backend: jeden katalog na funkcję w `backend/app/` (`models.py`, `schemas.py`, `service.py`, `router.py`). Bez interfejsów repozytoriów i kontenera DI — zależności przez `Depends()`.
- Błędy dla klienta zgłaszaj przez `AppError(code, status)`; komunikat dodaj w `backend/app/locales/{pl,en}.json` pod kluczem `errors.<code>`.
- Każda zmiana modeli wymaga migracji Alembic (`uv run alembic revision --autogenerate`); test `test_models_match_migrations` pilnuje zgodności.
- Frontend: statyczne strony HTML + komponenty Alpine.js w osobnych plikach `.js`, bez bundlera. Teksty panelu w `frontend/shared/locales/{pl,en}.json` (oba pliki z tymi samymi kluczami). Ekran jest tylko po polsku.
- Dokumentacja i komunikaty po polsku; nazwy techniczne po angielsku.
- Przy zmianie poleceń `ddd`, zmiennych `.env` lub adresów API zaktualizuj `README.md` i `.env.example`.

## Kontrole przed commitem
```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest
cd frontend && npm run build
```
Jeśli któregoś polecenia nie da się uruchomić (np. brak bazy dla testów `db`), odnotuj to w opisie zmian.
