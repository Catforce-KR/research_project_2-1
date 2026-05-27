# AGENTS.md

## Project Overview

This repository is a research codebase for low-Reynolds-number helical propeller simulation using PyElastica and Resistive Force Theory (RFT).

The current implementation is intentionally transitional: `research_code.py` remains at the repository root as a single-file simulation script, while the project structure is prepared for later modularization under `src/helical_propeller/`.

## Research Goals

- Compare analytical RFT predictions with PyElastica / Cosserat rod simulation results.
- Study how helix pitch/radius ratio affects propulsion velocity and efficiency.
- Study how body-to-tail length ratio affects propulsion.
- Calibrate stiffness so the helical tail remains structurally valid during rotation.
- Validate discretization choices such as `n_elem` before relying on larger experiments.

## Tech Stack

- Language: Python
- Numerical libraries: NumPy, pandas
- Plotting: Matplotlib
- Rod simulation: PyElastica, imported in code as `elastica`
- Configuration: YAML via PyYAML
- Tests: pytest

## Python Environment Rules

- Use the Windows CPython virtual environment for all project commands.
- The project validation Python is `.venv\Scripts\python.exe`.
- The confirmed interpreter version is Python 3.13.3.
- Access to the Windows CPython base interpreter referenced by `.venv\Scripts\python.exe` is permanently allowed for this project.
- Use `.venv\Scripts\python.exe -m pytest tests` as the default test command.
- Use `.venv\Scripts\python.exe scripts\run_single.py` as the default single smoke run command.
- Do not use bare `python`.
- Do not use `.venv\bin\python.exe`.
- Do not use `C:\msys64\ucrt64\bin\python.exe`.
- If `.venv\Scripts\python.exe` is missing, report an environment problem instead of falling back to MSYS Python.
- Do not route execution through MSYS Python.

## Repository Structure

- `research_code.py`: current single-file simulation implementation. Do not perform large refactors here unless explicitly requested.
- `src/helical_propeller/`: future package location for modularized simulation code.
- `scripts/`: small runnable entry points, including smoke or single-run helpers.
- `configs/`: YAML configuration files for experiment defaults.
- `research/`: research proposal and planning documents.
- `docs/`: architecture, model assumptions, experiment plan, and validation notes.
- `data/raw/`: generated raw CSV data.
- `data/processed/`: cleaned or transformed CSV data.
- `results/figures/`: generated figures.
- `results/tables/`: generated summary tables.
- `results/reports/`: generated report outputs.
- `tests/`: lightweight automated tests.

## Coding Rules

- Keep changes small and reviewable.
- Prefer simple, maintainable implementations over broad rewrites.
- Do not introduce new dependencies unless necessary.
- Do not put secrets, API keys, personal information, or machine-specific credentials in tracked files.
- Preserve the current physical model, RFT equations, efficiency definitions, and stiffness check logic unless the user explicitly asks to change them.
- If `research_code.py` is modularized later, preserve behavior first and refactor in small validated steps.

## Numerical Simulation Rules

- Do not run long parameter sweeps unless the user explicitly requests them.
- Do not run H1/H2 sweeps, stiffness calibration sweeps, or convergence sweeps during routine setup or smoke tests.
- Do not run long parameter sweeps, stiffness calibration sweeps, or convergence sweeps unless explicitly requested.
- Use short smoke parameters when checking that the code can execute.
- If a simulation result was not actually executed, do not say it was executed.
- Clearly distinguish analytical prediction from PyElastica simulation result.
- If the physical model, RFT coefficients, analytical equations, efficiency definition, or stiffness check criteria change, update `docs/model_assumptions.md` in the same change.

## Test Rules

- Tests should be lightweight by default.
- Use `.venv\Scripts\python.exe -m pytest tests` for the default test run.
- Do not use bare `python` for tests.
- Do not run long simulations inside tests.
- Import tests and analytical helper tests are appropriate smoke tests.
- Any simulation execution in tests must use very small `n_elem`, `total_steps`, and `step_skip` values.
- If PyElastica is not installed, report the dependency issue clearly instead of claiming the model failed physically.

## Data And Result Storage Rules

- Generated raw CSV files belong in `data/raw/`.
- Generated processed CSV files belong in `data/processed/`.
- Generated figures belong in `results/figures/`.
- Generated summary tables belong in `results/tables/`.
- Generated reports belong in `results/reports/`.
- Do not commit large result files unless the user explicitly asks.
- Keep `.gitkeep` files so empty output directories remain visible in the repository.

## Working Log Rules

- `working_log.md` is a user-managed experiment and work journal wrote in Korean.
- Codex should edit `working_log.md` when a unique task has happened(not repeated).
- When adding an entry, keep it short and include the date, time, task name, executed command, key result, and any caution.

## Documentation Rules

- Update `README.md` when setup, execution, or project status changes.
- Update `docs/architecture.md` when module boundaries or file responsibilities change.
- Update `docs/model_assumptions.md` when physical assumptions, RFT coefficients, analytical formulas, efficiency definitions, or stiffness checks change.
- Update `docs/experiment_plan.md` when H1/H2 sweep plans or validation experiments change.
- Update `docs/validation.md` when test strategy or validation criteria change.

## Required Codex Response Summary

When completing a task in this repository, Codex should summarize:

```markdown
## 변경 요약
- ...

## 생성/이동한 파일
- ...

## 실행한 검증
- ...

## 실패 또는 주의사항
- ...

## 다음 단계 추천
- ...
```
