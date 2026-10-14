# Verification Test Report

## Purpose

These tests verify the numerical behaviour and selected input checks of the CO2 reconstruction functions. They use synthetic data with known answers, so the environmental sensor dataset is not required.

Verification checks whether the functions behave as intended. Accuracy when reconstructing real sensor measurements is assessed separately through gap-reconstruction experiments.

## Recorded run

- Date: 12 October 2026
- Environment: Google Colab
- Tested Git commit: `5336c76d82e6c604bc9d35b6960ecf1d7c8812f2`
- Python: 3.13.16
- NumPy: 2.1.3
- SciPy: 1.16.3
- Test runner: Python `unittest`
- Result: **13 tests passed; no failures or errors**
- Reported test execution time: 0.027 seconds

Full output, including the run timestamp and individual test results, is preserved in [test_results.txt](evidence/test_results.txt). The recorded execution time excludes cloning the repository and starting the Python process; it is not a benchmark of reconstruction performance.

## Verification after source-documentation updates

A fresh GitHub clone was checked in Google Colab on 12 October 2026 after expanding the source comments and docstrings.

- Tested source commit: `47716c61643c558dbe519261ab3a073377c2366c`
- Python syntax compilation: passed for all source modules.
- Repository unit tests: all 13 passed, with no failures or errors.
- Reported unit-test execution time: 0.006 seconds.
- Executable documentation examples in `reconstruct.py` and `models.py`: passed.

The commands were:

```bash
python -m compileall -q src
python -m unittest discover -s tests -v
python -m doctest src/reconstruct.py src/models.py
```

Saved commands and output are available in
[sensor_gap_exploration.ipynb](sensor_gap_exploration.ipynb).

This rerun checks the updated source and documentation examples.
It does not extend the unit-test coverage to the data loaders or
establish real-data reconstruction accuracy. The execution time is
not a reconstruction-performance benchmark.

## Test coverage

| Test | Expected behaviour | Result |
| --- | --- | --- |
| Linear interpolation: known straight line | Recover the known values between observations | Pass |
| Previous-value baseline | Repeat the last observed CO2 value | Pass |
| Reconstruction: time outside gap | Raise `ValueError` | Pass |
| Spline: uneven observation times | Recover 406, 412 and 420 ppm from a known straight line | Pass |
| Spline: observation points | Reproduce the supplied observed values | Pass |
| Spline: invalid observations | Reject insufficient or mismatched observations, invalid shapes, unordered or repeated times, and nonfinite values | Pass |
| Spline: invalid queries | Reject nonfinite, incorrectly shaped or out-of-range query times | Pass |
| Regression: known equation | Predict 403.8 and 408.2 ppm for new feature combinations | Pass |
| Regression: fixed training scaling | Preserve training means and scales; predict the same value independently of other prediction rows | Pass |
| Regression: invalid prediction features | Reject incorrect feature shapes and nonfinite values | Pass |
| Regression: invalid training data | Reject invalid feature shapes, mismatched or nonfinite targets, and insufficient training rows | Pass |
| Regression: constant feature | Reject a feature with no training variation | Pass |
| Regression: rank-deficient training | Reject dependent features that cannot uniquely identify all coefficients | Pass |

Several tests contain multiple invalid-input cases checked using `subTest`. The total of 13 refers to test methods, rather than the number of individual input cases.

## Numerical reference answers

The spline straight-line test uses:

`CO2(t) = 400 + 2t`

At query times of 3, 6 and 10 seconds, the expected values are 406, 412 and 420 ppm.

The regression test uses the independently specified synthetic relationship:

`CO2 = 400 + 2(T - 20) + 0.5(H - 40) - 0.1(P - 1000)`

Here, T is temperature in degrees Celsius, H is humidity in percent, and P is pressure in mb.

For feature rows `[21, 44, 1002]` and `[23, 46, 1008]`, the expected predictions are 403.8 and 408.2 ppm. These rows are not included in the synthetic training data.

The numerical comparisons in `tests/test_models.py` use an absolute tolerance of `1e-9` ppm and a relative tolerance of zero. This tolerance checks numerical implementation on synthetic examples; it does not represent real sensor accuracy.

## Reproducing the tests

From the repository's main directory, in a Python environment with NumPy and SciPy installed, run:

```bash
python -m unittest discover -s tests -v
```

The tests are located in:

- `tests/test_reconstruct.py`
- `tests/test_models.py`

They exercise functions in:

- `src/reconstruct.py`
- `src/models.py`

The recorded run used a fresh clone of the repository to test the committed source files.

## Additional gap-position experiment checks

The additional experiment completed on 14 October 2026 compares four reconstruction methods across ten selected 24-hour viewing windows.

Each window contains separately simulated gaps near hours 6, 12 and 18 from the window start. At each position, 6, 18 and 36 readings are hidden.

This produces:

- 10 selected viewing windows.
- 90 simulated gap comparisons.
- 360 method-result records.
- 30 generated figures, of which four are included in the repository.

These are real-data evaluation cases, not additional unit tests. The repository unit-test count remains 13.

### Workflow checks

| Check | Expected behaviour | Recorded outcome |
| --- | --- | --- |
| Window selection | Use a fixed chronological selection rule without selecting days by reconstruction error | Selection procedure recorded |
| Gap eligibility | Keep each gap and its observed context inside the selected day and evaluation period | All 90 planned gaps eligible |
| Timestamp continuity | Reject a gap/context window with an adjacent interval exceeding 30 minutes | No planned gaps excluded |
| Hidden CO2 separation | Exclude hidden CO2 readings from reconstruction inputs, including spline context | Checked by the workflow |
| Regression training | Fit coefficients and scaling using only the first chronological 50% | Training restricted to the earlier segment |
| Prediction shape | Return one estimate per hidden reading | Checked for each method and gap |
| Numerical validity | Produce finite predictions | Checked for each method and gap |
| Output completeness | Record all four methods for each eligible gap | 90 gap comparisons and 360 method records |
| Error calculation | Recalculate MAE and RMSE from saved individual predictions | Matched reported errors within absolute tolerance `1e-9`, with relative tolerance zero |

For this experiment, MAE and RMSE are calculated as:

`MAE = mean(abs(predicted - recorded))`

`RMSE = sqrt(mean((predicted - recorded)^2))`

The independent recalculation checks consistency between the saved predictions and reported metrics. It does not independently establish the physical accuracy of the sensor or prove that every part of the workflow is correct.

### Evidence

The experiment code and recorded output are in
[sensor_gap_exploration.ipynb](sensor_gap_exploration.ipynb).

The saved records are:

- [Complete method errors and gap durations](results/co2_position_cases/position_errors.csv)
- [Individual recorded values and predictions](results/co2_position_cases/hidden_predictions.csv)
- [Summary by gap position, gap size and method](results/co2_position_cases/position_summary.csv)
- [MAE and RMSE winners, including ties](results/co2_position_cases/position_winners.csv)
- [Selected viewing windows](results/co2_position_cases/selected_windows.csv)
- [Excluded-gap record](results/co2_position_cases/excluded_gaps.csv)
- [Selection procedure, checks and limitations](evidence/selection_details.json)

The excluded-gap CSV contains its column headings but no excluded cases because all 90 planned gaps passed the eligibility checks.

### Reproducing the experiment

Open the repository notebook in Google Colab and run its cells in order, uploading the original environmental sensor ZIP when prompted.

The final gap-position comparison cell generates the result tables and all 30 figures, displays three previews, and downloads `co2_position_cases.zip`.

The downloaded experiment ZIP groups its generated outputs together. In this repository, the CSV records are stored under `results/co2_position_cases/`, the four selected case figures under `figures/`, and the selection record under `evidence/`.

The reconstruction functions were reused without changing their algorithms. The additional notebook workflow therefore does not require different source-module documentation solely because new cases and figures were added.

### Scope and limitations

These checks support the consistency of the recorded gap-position experiment. They are separate from the synthetic unit tests and do not provide exhaustive testing of the data loader or evaluation workflow.

Some simulated gaps overlap, so the 90 comparisons should not be treated as statistically independent samples. The data periods had already been examined and are not an untouched final test set.

Regression assumes temperature, humidity and pressure remain available during the CO2 gap. The experiment therefore represents missing CO2 measurements rather than failure of every sensor channel.

Four figures were selected after reviewing the results to illustrate different outcomes. Overall conclusions should use the complete results rather than only those selected figures.

## Interpretation and limitations

All 13 tests passed at the recorded commit. This supports the tested numerical behaviour and input validation of the reconstruction functions.

These tests do not verify the complete CSV-loading and evaluation workflow, cover every possible input, or establish accuracy on real sensor gaps. A spline can pass its verification tests while producing substantial reconstruction errors on fluctuating measurements. Regression can recover a known synthetic relationship while performing poorly on real CO2 data.

The additional gap-position checks support output completeness, separation of hidden targets from reconstruction inputs, and consistency of the saved error calculations. They do not replace the unit tests or establish generalisation to other sensors.

Real-data accuracy, sensitivity to gap length, and engineering suitability must therefore be evaluated separately. The test suite should be rerun after source changes, and this report and its evidence updated when relevant.
