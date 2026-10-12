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

Full output, including the run timestamp and individual test results, is preserved in [test_results.txt](test_results.txt). The recorded execution time excludes cloning the repository and starting the Python process; it is not a benchmark of reconstruction performance.
## Verification after source-documentation updates

A fresh GitHub clone was checked in Google Colab on 12 October 2026 after expanding the source comments and docstrings.

- Tested source commit: `47716c61643c558dbe519261ab3a073377c2366c`
- Python syntax compilation: passed for all source modules.
- Repository unit tests: all 13 passed, with no failures or errors.
- Reported unit-test execution time: 0.006 seconds.
- Executable documentation examples in `reconstruct.py` and `models.py`: passed.

The commands were:

    python -m compileall -q src
    python -m unittest discover -s tests -v
    python -m doctest src/reconstruct.py src/models.py

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

## Interpretation and limitations

All 13 tests passed at the recorded commit. This supports the tested numerical behaviour and input validation of the reconstruction functions.

These tests do not verify the complete CSV-loading and evaluation workflow, cover every possible input, or establish accuracy on real sensor gaps. A spline can pass its verification tests while producing substantial reconstruction errors on fluctuating measurements. Regression can recover a known synthetic relationship while performing poorly on real CO2 data.

Real-data accuracy, sensitivity to gap length, and engineering suitability must therefore be evaluated separately. The test suite should be rerun after source changes, and this report and its evidence updated when relevant.
