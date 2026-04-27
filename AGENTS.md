# AGENTS.md 

## Fast start (local)
- Python is pinned to `>=3.14` (`pyproject.toml`); use `uv`.
- Load env from `secrets/.env` (CLI auto-loads `secrets/.env`, then falls back to `.env`).
- Install deps: `uv sync`
- Run chat: `uv run tutor-assistant chat`
- Useful chat flags: `--thread-id <id>`, `--show-reasoning`, `--hide-tools`

## Fast start (Docker)
- `./run-agent.sh` defaults to `chat` and builds `tutor-assistant-local` each run.
- Container mounts repo at `/data` and forces paths:
  - `GOOGLE_CREDENTIALS_PATH=/data/secrets/credentials.json`
  - `GOOGLE_TOKEN_PATH=/data/secrets/token.json`
  - `TUTOR_AGENT_MEMORY_PATH=/data/memory/.agent_memory.json`
  - `TUTOR_LOG_DIR=/data/.logs`

## Verification commands
- Lint: `uv run ruff check .`
- Unit tests: `uv run pytest tests/unit`
- Full tests: `uv run pytest`
- Single test: `uv run pytest tests/unit/test_agent_graph.py::test_build_system_prompt_includes_critical_action_approval_rules`
- Integration tests are opt-in and marked `@pytest.mark.integration`; by default they skip.

## Integration test toggles (real APIs)
- Global toggle: `GOOGLE_ENABLE_ALL_INTEGRATION_TESTS=1`
- Per-suite toggles used in tests:
  - `GOOGLE_ENABLE_ONBOARDING_INTEGRATION_TEST=1`
  - `GOOGLE_ENABLE_DAILY_SUMMARY_INTEGRATION_TEST=1`
  - `GOOGLE_ENABLE_HOMEWORK_INTEGRATION_TEST=1`
  - `GOOGLE_ENABLE_VACATION_INTEGRATION_TEST=1`
  - `GOOGLE_ENABLE_GMAIL_INTEGRATION_TEST=1`

## Repo map (actual entrypoints)
- CLI entrypoint: `src/tutor/agent/cli.py` (`tutor-assistant` script -> `tutor.agent.cli:main`).
- Runtime chat agent assembly: `src/tutor/agent/graph.py` + `src/tutor/agent/tools/__init__.py`.
- Core use-case services:
  - `src/tutor/daily_summary/service.py`
  - `src/tutor/homework/service.py`
  - `src/tutor/onboarding/service.py`
  - `src/tutor/vacation/service.py`
  - `src/tutor/drive_cleanup/service.py`

## High-signal gotchas
- CLI parser currently exposes only `chat`, `memory-set`, `memory-list`, `memory-delete` (do not assume onboarding/vacation subcommands exist).
- Memory is namespaced by `thread_id` (default `teacher-cli`) and persisted to JSON (`TUTOR_AGENT_MEMORY_PATH` or `.agent_memory.json`).
- Critical action contract is enforced in tools:
  - `onboard_student` requires explicit approval (`approved_by_user=true`).
  - `prepare_vacation_notifications` requires approval only when `send_emails=true`.
- Tool self-repair policy is built into wrappers: up to 3 retries, then explicit stop/error message.
- Passthrough tools must return raw output wrapped as `<tool_output>...</tool_output>` (`build_daily_summary`, `onboard_student`, `prepare_vacation_notifications`, `upload_homework_for_day`).

## Environment variable mismatch to watch
- Two different Drive parent env names are used in code:
  - `GOOGLE_DRIVE_STUDENT_NOTES_FOLDER_ID` (agent tool defaults, daily summary notes provider)
  - `GOOGLE_DRIVE_PARENT_FOLDER_ID` (onboarding/homework providers and integration tests)
- `secrets/.env.example` documents `GOOGLE_DRIVE_STUDENT_NOTES_FOLDER_ID`; if homework/onboarding fails to find folders, set `GOOGLE_DRIVE_PARENT_FOLDER_ID` too.

## Auth/logging behavior
- Google auth files default to `secrets/credentials.json` and `secrets/token.json`; `login_google_user` can generate credentials from OAuth env vars and run local browser auth.
- Chat telemetry writes per-session logs under `.logs/` (or `TUTOR_LOG_DIR`) using `chat-<thread-id>-<timestamp>` in filenames.
