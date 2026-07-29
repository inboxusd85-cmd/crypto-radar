# Crypto Radar — следующий этап: эксплуатационный контур и decision-first UX

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Перевести текущий read-only radar из проверенного MVP в надёжный эксплуатационный контур: регулярный сбор рынка → outcome worker → объяснимый UI → наблюдаемость → первые live smoke/cron проверки.

**Architecture:** Сохранить текущую read-only архитектуру FastAPI + SQLite + React/Vite. Не добавлять автоторговлю, wallet/signing или order API. Следующий вертикальный срез — сделать worker и freshness видимыми не только как telemetry, но и как decision-ready качество данных.

**Tech Stack:** Python 3.11, FastAPI, SQLite, pytest через `.venv/bin/pytest`, React/TypeScript, Vitest, Vite, Hermes Cron.

---

## Текущее состояние

- Backend suite: 166 passed.
- Frontend: 8 test files / 19 tests passed.
- Production build проходит.
- Health API отдаёт нормализованный `outcomes.worker.status`.
- UI показывает `Работает` / `Ошибка worker`.
- Legacy SQLite state без `status` покрыт regression-тестом.
- Канонический `pytest` отсутствует в PATH; использовать `.venv/bin/pytest`.
- Git metadata в `/Users/roman/crypto-radar` сейчас недоступна, поэтому коммиты не планировать до проверки репозитория.

---

## Task 1: Зафиксировать freshness-контракт health API

**Objective:** Показывать, насколько свежи market collector и outcome worker, а не только завершился ли последний запуск.

**Files:**
- Modify: `src/crypto_radar/web/app.py`
- Modify: `src/crypto_radar/outcomes.py` или актуальный state store
- Test: `tests/test_outcome_review.py`
- Test: `tests/test_web_app.py`

**TDD:**
1. Добавить failing tests для `worker.completed_at`, `worker.age_seconds` и явного `stale: true` после configurable threshold.
2. Запустить targeted test через `.venv/bin/pytest ... -q`.
3. Добавить минимальную нормализацию в health response; не мигрировать legacy SQLite.
4. Повторить targeted и полный backend suite.

**Acceptance criteria:**
- Legacy state продолжает работать.
- `status` и freshness вычисляются в одном месте.
- Не считать `pending` ошибкой.
- Ошибка worker и stale worker различаются.

---

## Task 2: Decision-first health UI

**Objective:** На странице состояния сначала показывать verdict по качеству данных, затем raw telemetry.

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css` или актуальный CSS-файл
- Test: `web/src/App.test.tsx`

**TDD:**
1. Добавить fixtures для `ok`, `stale`, `error`, `not_started`.
2. Проверить RED на тексте и tone карточки.
3. Реализовать компактные verdict labels: `Данные свежие`, `Данные устарели`, `Ошибка worker`, `Ещё не запускался`.
4. Сырые `attempted/ready/pending/errors/completed_at` оставить в detail.
5. Прогнать `npm test -- --run` и `npm run build`.

**Acceptance criteria:**
- Без горизонтального scroll.
- Русский decision-first UI.
- Ошибка и stale визуально различимы.
- Existing API/overview/review pages не ломаются.

---

## Task 3: Operational launcher contract

**Objective:** Сделать collector и worker пригодными для безопасного recurring запуска.

**Files:**
- Modify: `scripts/run_outcome_worker.sh`
- Modify: `scripts/run_indicators_pipeline.sh`
- Test: `tests/test_outcome_worker_launcher.py`
- Test: `tests/test_cli.py` или отдельный launcher test
- Modify: `README.md`

**Checks:**
- stdout содержит одну валидную JSON-строку.
- exit code non-zero только при реальной ошибке.
- `HISTORY`, `LIMIT`, `ASSETS`, `TIMEFRAMES` явно документированы.
- Повторный запуск idempotent.
- Legacy DB не требует ручной миграции.

**Verification:**
- `.venv/bin/pytest tests/test_outcome_worker_launcher.py -q`
- shell smoke на временной SQLite.
- JSON parse stdout.

---

## Task 4: Hermes Cron — только после launcher smoke

**Objective:** Включить регулярные job’ы в Hermes Cron после подтверждения локального контракта.

**Prerequisite:** Сначала загрузить `hermes-agent` skill и свериться с актуальной документацией Hermes.

**Jobs:**
1. Market indicators collector — recurring interval, project `workdir=/Users/roman/crypto-radar`.
2. Outcome worker — recurring interval после collector с достаточным offset.
3. Optional health watchdog — только alert при stale/error, без спама при `ok`.

**Acceptance criteria:**
- Jobs имеют self-contained prompts.
- Не создаётся live social cron до ручной OAuth setup.
- Watchdog не рекурсивно создаёт новые jobs.
- Проверить job list и один ручной run.

---

## Task 5: Live smoke и эксплуатационная полировка

**Objective:** Проверить полный read-only цикл на локальном production-like сервере.

**Checks:**
- `/health` отдаёт SPA.
- `/api/v1/health` отдаёт normalized worker state.
- `/api/v1/overview`, `/api/v1/events`, `/api/v1/reviews` отвечают без 5xx.
- Browser console errors = 0.
- `scrollWidth - clientWidth = 0`.
- Проверить stale/error UI через deterministic API fixture или test-only server seam.

**Verification commands:**
```bash
.venv/bin/pytest -q
cd web && npm test -- --run && npm run build
```

---

## Риски и ограничения

- Не считать отсутствие `pytest` в PATH падением проекта; canonical fallback — `.venv/bin/pytest`.
- Не добавлять торговое исполнение или credentials.
- Не смешивать freshness, worker errors и provider availability в один boolean без объяснения.
- Не создавать cron для X/social live до ручной OAuth настройки.
- Перед коммитом проверить реальный git root; текущий `/Users/roman/crypto-radar` сообщает, что это не git repository.

## Рекомендуемый следующий вертикальный срез

Начать с **Task 1: freshness-контракт health API**, затем сразу Task 2. Это даст пользователю полезный operational verdict и устранит главный оставшийся разрыв между telemetry и decision-first UX.
