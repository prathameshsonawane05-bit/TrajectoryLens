# Evaluation

Scores are type-level precision and recall. A run counts once per rule. The summary screen counts finding rows, so its ignored-error bar on the training samples is 7 while this score counts 5 runs. The labels were written by hand. The v1 labels were not changed after scoring, and the v2 labels were not changed after scoring.

## v1 results, before any tuning

Fifteen held-out runs from `scripts/generate_heldout.py`, scored before the formatting change.

```text
rule                     tp   fp   fn  precision   recall
---------------------------------------------------------
command_loop              0    0    2        N/A    0.000
edit_then_fail            1    0    0      1.000    1.000
false_success_claim       1    0    0      1.000    1.000
gave_up_early             1    0    0      1.000    1.000
symptom_fix               0    0    2        N/A    0.000
ignored_error             2    1    0      0.667    1.000
no_test_run               1    0    0      1.000    1.000
```

Precision is undefined when tp and fp are both 0. Those two cells were previously printed as 1.000 by that convention. Recall 0.000 is a real ratio.

Five runs disagreed with the labels:

- `hold-03-paraphrased-symptom` expected `symptom_fix`, predicted nothing. Three edits of the cart file sit between the same bug, written as "total is 10 but expected 12", "was 10, wanted 12", and "came out 10 instead of 12". The rule keeps a signature only when the text matches.
- `hold-04-abs-path-symptom` expected `symptom_fix`, predicted nothing. The edits are `cart/total.py`, `/tmp/work/cart/total.py`, and `cart/total.py`, with `AssertionError: total was 9` in both gaps. The absolute path was stored as a different file.
- `hold-06-dot-slash-loop` expected `command_loop`, predicted nothing. The agent runs `python src/cart.py --check`, then `python ./src/cart.py --check`, then the first command again, with the same four-line result. The `./` made the middle command a different string.
- `hold-07-wide-gap-loop` expected `command_loop`, predicted nothing. `python toy_store/list_bins.py` returns `bins: 3` three times, with six other steps between the second and third. A repeat joins a loop only when it falls within five steps of the previous repeat.
- `hold-09-paraphrased-ack` expected nothing, predicted `ignored_error`. `import toybox.ledger` raises `ModuleNotFoundError`, and the next message says the ledger helper is missing and will be added. The rule looks for the exception name, the path, or the copied stderr line.

## Formatting change

Path comparison now strips a leading `./`, converts backslashes to slashes, and treats an absolute path and a relative path as the same file when the longer path ends with a slash plus the shorter path. `command_loop` normalizes each command token the same way, so a `./` prefix or a backslash does not split two commands. The command window is unchanged. Signature text and error paraphrases are unchanged.

On the same v1 runs, after that change:

```text
rule                     tp   fp   fn  precision   recall
---------------------------------------------------------
command_loop              1    0    1      1.000    0.500
edit_then_fail            1    0    0      1.000    1.000
false_success_claim       1    0    0      1.000    1.000
gave_up_early             1    0    0      1.000    1.000
symptom_fix               1    0    1      1.000    0.500
ignored_error             2    1    0      0.667    1.000
no_test_run               1    0    0      1.000    1.000
```

`hold-04-abs-path-symptom` and `hold-06-dot-slash-loop` now match. The labeled training set stayed at 1.000 precision and recall for every rule.

## Known limitations

These three v1 misses are unchanged on purpose.

- `hold-03-paraphrased-symptom`: restated assertions are not the same signature. An LLM labeler could read the three sentences and decide they describe one cart-total failure even though none is a copy of another.
- `hold-07-wide-gap-loop`: the five-step window still drops the third `list_bins.py` run. An LLM labeler could see that the same command returned `bins: 3` three times and call that a loop even with other work in between, instead of using a fixed step count.
- `hold-09-paraphrased-ack`: a message that restates a missing module still counts as ignoring the error. An LLM labeler could read "the ledger helper is missing, so I will add that module" and recognize it as a response to the failed import, without the exception name or the copied traceback.

## v2 results

Ten new runs from `scripts/generate_heldout_v2.py`, labeled before this score and not used to change any rule.

```text
rule                     tp   fp   fn  precision   recall
---------------------------------------------------------
command_loop              1    0    0      1.000    1.000
edit_then_fail            2    0    0      1.000    1.000
false_success_claim       2    0    0      1.000    1.000
gave_up_early             1    0    0      1.000    1.000
symptom_fix               1    0    0      1.000    1.000
ignored_error             1    0    0      1.000    1.000
no_test_run               1    0    0      1.000    1.000
```

No v2 run disagreed with its label.

## Before and after

| rule | v1 before | v1 after formatting | v2 |
| --- | --- | --- | --- |
| command_loop | N/A / 0.000 | 1.000 / 0.500 | 1.000 / 1.000 |
| edit_then_fail | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| false_success_claim | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| gave_up_early | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| symptom_fix | N/A / 0.000 | 1.000 / 0.500 | 1.000 / 1.000 |
| ignored_error | 0.667 / 1.000 | 0.667 / 1.000 | 1.000 / 1.000 |
| no_test_run | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |

Each cell is precision / recall. The v1 recall gains are the absolute-path file match and the `./` command match. v2 is a separate set of 10 runs, scored once.
