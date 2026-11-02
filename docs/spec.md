# Спецификация Discovery → Jira Agent

Основано на инструкции пользователя от 02.11.2026. Это целевой контракт MVP, а не описание уже реализованных функций. Порядок работы и текущий статус — в [плане](plan.md).

## Цель и объём

Демо превращает неструктурированный текст разговора в проверенные человеком Jira user stories. Основной сценарий без регистрации должен занимать менее двух минут: выбор проекта и разговора → извлечение требований с цитатами → проверка по спецификации → редактирование историй → Approve → Jira preview.

Проект должен показывать discovery, RAG, LangGraph, structured output, evals с порогом, LangSmith traces, стоимость прогона, human-in-the-loop, идемпотентность, retries и работающий Next.js UI.

В MVP входят один вымышленный клиент, одна спецификация, шесть разговоров, минимум 12 размеченных eval-кейсов и опубликованное демо. Вне объёма: аудиотранскрипция, авторизация и multi-user, Linear/Trello, story points, реальные клиентские данные и сложная дизайн-система.

## Архитектура

- Next.js App Router + TypeScript strict + Tailwind; UI на Vercel.
- Python 3.12 + FastAPI + LangGraph; Docker API на Render. Долгоживущие stateful-прогоны размещаются отдельно от web-хостинга.
- Postgres + pgvector на Neon: spec chunks и LangGraph checkpoints. Локально — Compose с образом `pgvector/pgvector`.
- LLM API: extraction, stories, classification, embeddings и judge. Провайдер и модели ещё не выбраны.
- LangSmith: traces, стоимость и eval datasets.
- Jira Cloud REST API v3: запись только после подтверждения человеком.

```text
extract → retrieve_spec → classify → write_stories → critic
                                         ↑           │
                                         └─ максимум один возврат
                                                     ↓
                           human_review (interrupt) → create_tickets
```

`human_review` использует LangGraph `interrupt`; возобновление — только через `POST /runs/{id}/approve`. Checkpointer — `langgraph-checkpoint-postgres`, чтобы прогон переживал рестарт. Критик может вернуть истории на доработку не более одного раза.

## Планируемая структура репозитория

```text
apps/
  api/
    app/
      main.py
      graph/          # nodes.py, state.py, graph.py
      rag/            # ingest.py, chunking.py, retrieve.py
      jira/client.py  # dry-run и реальная запись
      schemas.py
      config.py
    tests/
    pyproject.toml
    Dockerfile
  web/
data/demo/<project>/
  spec.md
  transcripts/*.md
evals/
  cases/*.json
  run_evals.py
docs/
  decisions.md
  case-study.md
docker-compose.yml
.env.example
```

Каталоги и команды запуска добавляются вместе с работающей реализацией. Операционные команды проверяются из указанного рабочего каталога перед публикацией в README.

## Контракты данных

При реализации источником истины становятся Pydantic-модели в `apps/api/app/schemas.py`. Минимальный согласованный контракт:

```python
class Requirement(BaseModel):
    id: str
    text: str
    type: Literal["functional", "non_functional", "constraint"]
    priority: Literal["must", "should", "could"]
    quote: str
    speaker: str
    status: Literal["new", "duplicate", "conflict", "unclear"] | None = None
    spec_refs: list[str] = Field(default_factory=list)
    note: str | None = None

class Story(BaseModel):
    id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: list[str]
    requirement_ids: list[str]
    idempotency_key: str
```

Цитата берётся из исходного разговора без переписывания. Код проверяет непустое вхождение после нормализации пробелов и регистра; неподтверждённые требования отбрасываются. `spec_refs` — идентификаторы найденных chunks; `note` объясняет конфликт или неясность. Acceptance criteria должны быть проверяемыми, предпочтительно Given/When/Then.

`idempotency_key` — SHA-256 нормализованного title и requirement IDs. Правила нормализации и сериализации фиксируются с тестами при реализации. Редактирование и подтверждение историй не должно позволять обходить валидацию или создавать дубликаты при повторе запроса.

`RunResult` должен содержать требования, истории, открытые вопросы, статус, стоимость, latency, trace URL и результат Jira/dry-run. Полную модель определяем в фазе контрактов.

## API

| Метод и путь | Контракт |
|---|---|
| `GET /health` | Доступность API; точный ответ фиксируется в фазе 2 |
| `GET /projects` | Список демопроектов |
| `POST /runs` | `{project_id, transcript}` → `{run_id}`; запуск graph в фоне |
| `GET /runs/{id}` | Текущее состояние: requirements, stories, questions, cost_usd, latency_ms, trace_url |
| `GET /runs/{id}/events` | SSE: `node_started`, `node_finished`, `awaiting_review`, `done`, `error` |
| `POST /runs/{id}/approve` | `{stories}` → возобновление graph и tickets либо dry-run preview |

Входные данные, история редактирования и допустимость approve для текущего состояния валидируются на сервере. Формат ошибок, доставка preset-транскриптов и политика переподключения SSE уточняются в соответствующих фазах.

## Надёжность и стоимость

- Все LLM-вызовы идут через один helper с учётом токенов и цены. Превышение `MAX_COST_PER_RUN_USD` завершает прогон с ошибкой.
- Jira-записи только из `create_tickets` после Approve. Перед create — поиск по label `idem-<key>`, найденную задачу повторно не создавать.
- На 429/5xx — экспоненциальная задержка, максимум три повтора после исходной попытки. Неоднозначный ответ create требует проверки существования задачи перед повтором.
- Поиск по label сам по себе не защищает от одновременных approve: в фазе 7 необходима проверенная защита от конкурирующих записей.
- `JIRA_DRY_RUN=true` по умолчанию, публичный режим всегда dry-run независимо от UI. Секреты только в env, без попадания в репозиторий или логи.
- Preset cache и дневной LLM-бюджет нужны для публичного демо.

## Оценка качества

Данные: шесть размеченных разговоров плюс минимум шесть коротких synthetic cases. В каждом случае — эталонные требования, конфликты и ожидаемые истории. RAG разбивает спецификацию по заголовкам с fallback по размеру и извлекает top-5 chunks; отдельно измеряется recall@5.

| Метрика | Метод | Критерий |
|---|---|---|
| Requirement precision / recall | Сопоставление с gold по embedding similarity ≥ 0.8 | Падение ниже зафиксированного baseline − 0.05 завершает evals ошибкой |
| Grounding rate | Доля требований с подтверждённой цитатой после фильтра | 1.0; пустой результат не выдавать за доказательство качества |
| Conflict F1 | Сравнение с gold conflicts | Не ниже baseline − 0.05 |
| Story quality | LLM-judge 1–5: INVEST и testable AC; калибровка на 10 ручных оценках | Среднее ≥ 3.5 |
| Cost/run и p95 latency | LLM-helper / LangSmith | Отчётные метрики |

Baseline фиксируется после первого измерения и не пересчитывается автоматически ради прохождения проверки. Все результаты публикуются с N. CI выполняет небольшой eval subset на PR и падает ниже порога; изменения промпта или модели требуют запуска evals перед merge. Реальные числа, GIF и case study добавляются только после проверки.

## Итоговая приёмка

Новый посетитель открывает Vercel URL без регистрации, запускает preset, видит требования с цитатами и обнаруженный конфликт, редактирует историю, подтверждает её и получает Jira preview менее чем за две минуты. README содержит измеренные eval-метрики с N и стоимость прогона.
