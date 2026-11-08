# Design

TrajectoryLens stores coding-agent trajectories and labels failures with small deterministic rules. The people using it review evaluation tasks. The rules are a first pass, not a judgment.

## Sample data

Every trajectory in this repository is synthetic. The tasks, file paths, commands, and model names were invented for this project. Names such as harbor-small, lumen-lite, and kite-mini are placeholders. A higher finding count for one of those names does not mean that model is worse. The counts only show that the charts and filters have something to display.

## Decisions

- A run is stored in SQLite. `POST /runs` writes the steps and immediately replaces that run's findings. `POST /analyze-all` does the same for every stored run, so a second call does not duplicate rows.
- `GET /runs` returns summaries without steps. `GET /runs/{run_id}` returns the steps. `GET /summary` returns pass/fail totals, finding counts by type, finding counts by model, and the five most common failure types.
- Step indexes start at 0 and strictly increase. Gaps are allowed.
- Each rule is a function in `backend/app/analyzer/rules.py` decorated with `@rule`. It receives the run in memory and returns findings. The analyzer does not need the database.
- Findings are compared as sets of types when measuring precision and recall. One run counts once per rule, even if that rule fires on more than one step.
- Paths are compared after stripping a leading `./` and turning backslashes into slashes. An absolute path and a relative path match when the longer path ends with a slash plus the shorter path, and the shorter path includes a directory. A bare filename such as `utils.py` joins a longer path only when the run contains exactly one candidate. `src/utils.py` and `tests/utils.py` stay different files.
- `command_loop` treats `./` and backslashes in the command text as the same command. A later repeat joins the loop only when it is within five steps of the previous repeat and the output is the same or nearly the same.
- There is no authentication. The app is a local review tool.

## Limitations

The rules are heuristics. They miss paraphrased errors and repeated commands that sit far apart, and they can flag a message that a person would read as a response to the error. False positives and false negatives are expected. The labeled sets are small: 40 training runs, 15 held-out runs, and 10 later held-out runs. Details are in [EVALUATION.md](EVALUATION.md).

An LLM-based labeler could read a restated assertion, a message that explains an error without copying it, and a repeated command with other work in between, then decide whether the rule should fire. That is a possible next step. It is not part of this version.
