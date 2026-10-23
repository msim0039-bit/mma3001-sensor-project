# Reconstructing missing indoor CO₂ sensor readings

## Engineering question

How accurately can missing indoor CO₂ readings be reconstructed using linear interpolation, cubic spline interpolation, and multiple linear regression, and how does reconstruction error change with gap length?

The engineering context is recovering incomplete records used in indoor air-quality and ventilation assessment. This project investigates offline reconstruction: observations after a gap are available before interpolation is performed. Reconstructed values are estimates, not replacement sensor measurements.

## Data and inputs

Source: MMA3001 Dataset 2, Monash Smart Infrastructure environmental sensor data.

The analysis uses sensor `6012002000869` from the original `5EnvSensor_MayToDec2024_180kRows.zip` supplied with the unit.

| Variable | Unit | Use |
| --- | --- | --- |
| Carbon dioxide | ppm | Reconstruction target |
| Temperature | °C | Regression input |
| Humidity | percent | Regression input |
| Pressure | mb | Regression input |
| Measurement timestamp | Unix seconds | Alignment and interpolation |

The audit found 29,341 CSV rows for this sensor and 13,800 distinct CO₂ timestamps. The four selected variables contain 13,800 aligned observations.

`src/compare.py` reads the ZIP directly, which must contain exactly one CSV with `sensorid` and `jsondata` columns. It collapses identical repeated measurements, aligns variables by exact timestamp, and sorts observations chronologically. It rejects invalid or nonfinite measurements, conflicting values, absent variables, and incomplete alignment.

Obtain the original ZIP from the unit's Dataset 2 materials. Keep it outside this public repository. Occupancy data and the example data labelled “Do not use” are not used.

## Methods

| Method | Information used | Role |
| --- | --- | --- |
| Previous value | Last observed CO₂ value before the gap | Baseline |
| Linear interpolation | CO₂ observations immediately before and after the gap; elapsed time | Main numerical method |
| Natural cubic spline | Four observed CO₂ readings on each side of the gap | Alternative numerical method |
| Multiple linear regression | Temperature, humidity and pressure; coefficients fitted on earlier CO₂ observations | Alternative regression method |

The spline uses natural boundary conditions and disables extrapolation. Its predictions are not clipped, so overshoot remains visible in the error evaluation.

Regression includes an intercept and three standardized predictors. Training means, standard deviations, and least-squares coefficients are calculated using training data only. Prediction reuses this scaling without refitting. Regression assumes the other three sensor variables remain available when CO₂ is missing.

Function inputs, outputs, units, assumptions and selected error checks are documented in the source docstrings and HTML documentation.

## Development comparison

Regression trains on the first 50% of chronological observations: 6,900 readings. Artificial gaps are evaluated in the following 25%: 3,450 readings.

For each simulated event, 6, 18 or 36 known CO₂ readings are hidden. All four methods estimate the same hidden targets. Hidden CO₂ values are excluded from reconstruction inputs.

Each event is evaluated independently. Candidate starts are separated by the gap size plus eight readings. A window is skipped if any adjacent timestamp interval exceeds 30 minutes.

Mean absolute error (MAE) and root mean square error (RMSE) compare estimates with the hidden measurements. Both are reported in ppm; smaller values indicate better reconstruction.

### MAE results

| Hidden readings | Gaps evaluated | Previous | Linear | Cubic spline | Regression |
| --- | --- | --- | --- | --- | --- |
| 6 | 246 | 13.05 | 9.81 | 18.49 | 35.19 |
| 18 | 132 | 17.04 | 11.62 | 39.31 | 35.47 |
| 36 | 78 | 30.75 | 16.60 | 75.38 | 35.62 |

### RMSE results

| Hidden readings | Previous | Linear | Cubic spline | Regression |
| --- | --- | --- | --- | --- |
| 6 | 18.16 | 12.82 | 23.61 | 45.93 |
| 18 | 23.49 | 15.22 | 52.10 | 46.16 |
| 36 | 41.68 | 21.88 | 102.62 | 46.34 |

The median elapsed intervals between observations surrounding the gaps are 79.98, 209.97 and 400.00 minutes respectively. A count of hidden readings is not itself a duration.

Linear interpolation has the lowest MAE and RMSE for all three gap sizes in this development segment. This supports it as the current preferred method for these experiments. The result does not establish that linear interpolation is best for every sensor, operating condition or missing-data pattern.

Full results: [co2_method_comparison.csv](results/co2_method_comparison.csv).

### Example gap

![Four methods reconstructing the first eligible 18-reading development gap](figures/co2_example_gap.png)

The figure shows the first eligible 18-reading gap, selected by chronological order rather than reconstruction error. It illustrates individual method behaviour; the aggregated errors above provide the broader comparison.

`figures/co2_gap_mae.png` and `src/evaluate.py` retain the earlier two-method experiment. Use `src/compare.py` and `results/co2_method_comparison.csv` for the current four-method comparison.

## Runtime comparison

The first eligible 18-reading development gap was used to compare the implemented functions. Timings exclude data loading and regression training; spline timing includes spline construction.

The timings below describe the original benchmark session preserved in `results/co2_runtime_comparison.csv` and `evidence/runtime_details.txt`. The notebook's later fresh-session run produced different timings. Runtime varies between Colab sessions, so exact timing values are not expected to reproduce; the saved benchmark and notebook rerun are separate records.

| Method | Median time per reconstruction call (ms) |
| --- | --- |
| Previous value | 0.008001 |
| Linear interpolation | 0.028145 |
| Natural cubic spline: four observations per side | 0.479558 |
| Regression prediction | 0.029136 |

Regression training on 6,900 observations took a median of 0.932163 ms, measured separately.

Each operation received a warm-up. Reconstruction timings are the median of seven batch averages, with 100 calls per batch. Training used 10 calls per batch.

These results describe one gap and one Colab session. Linear and regression prediction timings are close; they do not establish a meaningful speed difference. All measured reconstruction times were below 1 ms per call.

Evidence: [co2_runtime_comparison.csv](results/co2_runtime_comparison.csv) and [runtime_details.txt](evidence/runtime_details.txt). Benchmark code is in the notebook.

## Spline context sensitivity

Natural splines using two, four and eight observed readings per side were compared on identical hidden gaps within each gap size. Linear interpolation was evaluated on those same gaps.

| Hidden readings | Gaps evaluated | Linear MAE (ppm) | Spline: 2 per side | Spline: 4 per side | Spline: 8 per side |
| --- | --- | --- | --- | --- | --- |
| 6 | 156 | 9.12 | 15.19 | 18.42 | 18.46 |
| 18 | 101 | 12.74 | 31.75 | 41.46 | 41.59 |
| 36 | 66 | 17.40 | 48.06 | 68.32 | 68.73 |

Two observations per side gave the lowest spline errors among the tested settings. Adding more context did not improve accuracy in these experiments. Linear interpolation retained lower MAE and RMSE at every gap size.

These windows differ from the original development comparison because eligibility and spacing allow eight observations per side. Compare settings within this experiment rather than interpreting differences from the earlier table as a controlled improvement.

Full MAE and RMSE results: [co2_spline_sensitivity.csv](results/co2_spline_sensitivity.csv). Experiment code is in the notebook.

## Later-period temporal robustness

The same sensor's chronological 75%–100% segment was evaluated with regression still trained only on the first 50%. The original methods and the two-observation spline setting were compared on identical gaps.

| Hidden readings | Gaps evaluated | Previous MAE (ppm) | Linear | Spline: 4 per side | Spline: 2 per side | Regression |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | 246 | 10.17 | 8.32 | 15.99 | 13.32 | 23.73 |
| 18 | 132 | 13.94 | 9.47 | 36.13 | 26.52 | 23.69 |
| 36 | 78 | 15.93 | 11.69 | 63.86 | 48.22 | 23.28 |

Linear interpolation again produced the lowest MAE and RMSE at all three gap sizes. The two-observation spline improved on the four-observation spline but remained less accurate than linear interpolation.

This strengthens the method-selection evidence across two periods of this sensor. The later data had previously been examined, so this is a temporal robustness check, not an untouched final test set. It does not establish generalisation to other sensors.

Full results: [co2_temporal_robustness.csv](results/co2_temporal_robustness.csv). Experiment code is in the notebook.

## Gap-position comparison across ten daily windows

This additional experiment checks whether reconstruction performance changes when the missing gap occurs earlier, in the middle, or later within a 24-hour viewing window.

Ten windows were selected: five from the development period and five from the later period. Full 24-hour bins were anchored at each period's starting timestamp. Days eligible for all three middle-position gap sizes were spread chronologically using a fixed selection rule, without selecting them by reconstruction error.

Each selected day was evaluated with gaps near hours 6, 12 and 18 from the viewing-window start. At each position, 6, 18 and 36 readings were hidden. This gives 90 separately simulated gaps and 360 method results.

The 24 hours describe the viewing window, not the missing-gap duration. Positions are hours relative to the window start, not local clock times. Actual boundary intervals are recorded in the complete results.

Regression still trains only on the first chronological 50%, and the natural spline uses four observed CO₂ readings per side. All four methods estimate the same hidden readings within each comparison. Hidden CO₂ is excluded from reconstruction inputs; regression assumes temperature, humidity and pressure remain available.

Every gap and its observed context must fit inside the selected day and evaluation period. Adjacent timestamp intervals in the gap/context must not exceed 30 minutes. All 90 planned gaps passed these eligibility checks.

### Results by gap position

The table reports mean case MAE across the ten selected days, in ppm. Lower values indicate better reconstruction.

| Gap centre: hours from window start | Hidden readings | Previous | Linear | Cubic spline | Regression |
| --- | --- | --- | --- | --- | --- |
| 6 | 6 | 10.13 | **9.12** | 15.73 | 19.34 |
| 6 | 18 | 15.03 | **10.54** | 45.93 | 18.70 |
| 6 | 36 | 24.99 | **13.86** | 83.11 | 18.86 |
| 12 | 6 | 9.77 | **7.47** | 15.59 | 23.35 |
| 12 | 18 | 10.80 | **7.32** | 30.45 | 21.94 |
| 12 | 36 | 15.57 | **10.04** | 42.88 | 21.28 |
| 18 | 6 | 13.92 | **10.19** | 20.43 | 24.13 |
| 18 | 18 | 24.43 | **11.68** | 55.66 | 25.62 |
| 18 | 36 | 33.10 | **13.38** | 67.46 | 26.05 |

Linear interpolation had the lowest mean case MAE and mean case RMSE at every tested position and gap size. This supports linear as the overall preferred method for these selected windows.

However, the best method was not the same for every individual gap. Regression had the lowest MAE in four comparisons, and the spline in one. Previous value also performed best in several cases. MAE and RMSE selected different winner sets in five comparisons; the complete winner table records both metrics and preserves ties.

Linear's mean errors were lower near hour 12 than near hours 6 and 18 at each gap size. This describes the selected days only. It does not establish that interpolation is generally more accurate at a particular local time, or that gap position alone determines which method should be used.

### Complete result tables and selection records

The full results include all methods and all 90 simulated gaps:

- [Complete MAE, RMSE and gap-duration results](results/co2_position_cases/position_errors.csv)
- [Summary by position, gap size and method](results/co2_position_cases/position_summary.csv)
- [Best methods for each gap using MAE and RMSE](results/co2_position_cases/position_winners.csv)
- [Individual recorded CO₂ values and predictions](results/co2_position_cases/hidden_predictions.csv)
- [Dates and times of the ten selected windows](results/co2_position_cases/selected_windows.csv)
- [Excluded-gap record](results/co2_position_cases/excluded_gaps.csv)
- [Selection procedure, checks and limitations](evidence/selection_details.json)

To reproduce this experiment, run the notebook cells in order with the original environmental sensor ZIP. The final gap-position cell generates all result tables and 30 figures, then downloads `co2_position_cases.zip`. It displays three previews from Case 1. Four selected figures are included below.

The downloaded experiment ZIP groups its generated outputs together. In this repository, the CSV records are organised under `results/co2_position_cases/`, the four selected figures under `figures/`, and the selection record under `evidence/`.

### Selected case figures

These figures illustrate different outcomes. They were selected after reviewing the results, so they are examples rather than an unbiased sample for estimating overall performance. The complete result tables support the overall conclusions.

#### Case 1: gap position near hour 6

Linear has the lowest MAE for all three gap sizes. For the 36-reading gap, the recorded concentration generally decreases, and linear follows the overall change more closely than the constant previous-value estimate.

![Case 1: gaps near hour 6](figures/case_01_hour_06.png)

#### Case 2: gap position near hour 6

The MAE winner changes with gap size: previous value for six readings, regression for 18 readings, and linear for 36 readings. In the 18-reading gap, the recorded values fall below both boundary concentrations, which limits the straight-line estimate. Regression is closer in this particular case, while the spline introduces an upward overshoot.

![Case 2: gaps near hour 6](figures/case_02_hour_06.png)

#### Case 10: gap position near hour 12

Spline narrowly wins the six-reading gap by MAE: 3.54 ppm compared with linear's 3.63 ppm. Linear wins that gap by RMSE. The small difference and metric disagreement do not provide strong evidence that spline should be preferred. Linear has lower errors for the longer gaps in this figure.

![Case 10: gaps near hour 12](figures/case_10_hour_12.png)

#### Case 7: gap position near hour 18

Previous value narrowly beats linear by MAE for the six-reading gap, while linear wins the longer gaps. For the 36-reading gap, the spline produces a large downward overshoot and an MAE of 137.42 ppm, compared with 9.26 ppm for linear. This shows why a smooth curve should not automatically be treated as an accurate reconstruction.

![Case 7: gaps near hour 18](figures/case_07_hour_18.png)

### Verification and limitations

The workflow checks that gap/context indices remain inside the selected day, hidden indices are excluded from spline inputs, and predictions have the expected shape and finite values.

MAE and RMSE were recalculated from the individual predictions and matched the reported errors within absolute tolerance `1e-9`, with relative tolerance zero. The saved files contain 90 gap comparisons and 360 method results. These are evaluation cases, not additional repository unit tests.

Some simulated gaps overlap and should not be treated as statistically independent samples. The periods had already been examined, so this is an additional case comparison rather than an untouched final test.

The results support linear interpolation overall while showing exceptions for individual gaps. They do not establish a reliable rule for choosing a method from gap position alone, generalisation to other sensors, or agreement with the true physical CO₂ concentration.

## Repository guide

| File or folder | Purpose |
| --- | --- |
| `src/audit.py` | Audit repeated CO₂ records |
| `src/reconstruct.py` | Previous-value and linear reconstruction functions |
| `src/models.py` | Natural spline and regression functions |
| `src/compare.py` | Current four-method data-loading and evaluation workflow |
| `src/evaluate.py` | Earlier two-method evaluation |
| `tests/` | Synthetic numerical verification and invalid-input tests |
| `docs/` | Generated HTML source documentation and search file |
| `figures/` | Two original graphs and four selected gap-position figures |
| `results/` | Development, runtime, spline-sensitivity and temporal-robustness CSV tables |
| `results/co2_position_cases/` | Complete gap-position errors, summaries, winners, predictions and selection tables |
| `evidence/` | Recorded test output, reproduction results, benchmark details and experiment-selection record |
| `sensor_gap_exploration.ipynb` | Colab exploration and recorded checks |
| `requirements.txt` | Recorded analysis package versions |
| `TEST_REPORT.md` | Verification scope, results and limitations |
| `evidence/test_results.txt` | Actual output from the 13-test run |
| `evidence/reproduction_results.txt` | Evidence that the source comparison matches saved results |
| `results/co2_method_comparison.csv` | Current development comparison results |
| `figures/co2_example_gap.png` | Example four-method reconstruction plot |
| `LICENSE` | MIT licence for repository code |

## Run locally

The recorded verification environment used Python 3.13.16. Analysis package versions are pinned in `requirements.txt`. Git is needed for the clone command; alternatively, download and extract the repository ZIP from GitHub.

Clone the repository and enter its main directory:

```bash
git clone https://github.com/msim0039-bit/mma3001-sensor-project.git
cd mma3001-sensor-project
```

An isolated Python environment is recommended:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Install the analysis dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the audit and current comparison, replacing the example path with your original dataset ZIP path:

```bash
python src/audit.py "/path/to/5EnvSensor_MayToDec2024_180kRows.zip"
python src/compare.py "/path/to/5EnvSensor_MayToDec2024_180kRows.zip" --output results/co2_comparison_reproduced.csv
```

The comparison prints the aligned-observation count and error table, and saves a CSV in the specified location. Existing output files with the same name are replaced. It does not regenerate the example plot.

Optional arguments are available through:

```bash
python src/compare.py --help
```

## Run in Google Colab

Open [sensor_gap_exploration.ipynb in Colab](https://colab.research.google.com/github/msim0039-bit/mma3001-sensor-project/blob/main/sensor_gap_exploration.ipynb).

Save a copy to Google Drive before editing. Run the notebook cells in order, uploading the original environmental ZIP when prompted. File-upload and download cells use Google Colab-specific functions.

The notebook includes a fresh-clone test run and a source-script reproduction check. The dataset may need to be uploaded again after the Colab runtime resets.

## Verification and reproducibility evidence

Run the tests from the repository's main directory:

```bash
python -m unittest discover -s tests -v
```

All 13 tests passed in the recorded run on 12 October 2026. The tests check known numerical answers, selected invalid inputs, and fixed training scaling during regression prediction.

See [TEST_REPORT.md](TEST_REPORT.md) and [test_results.txt](evidence/test_results.txt) for the tested commit, environment and individual results.

A separate real-data reproduction check ran `src/compare.py` and compared its CSV with the saved notebook comparison. Method identifiers matched, and gap counts, errors and median boundary intervals matched with absolute tolerance `1e-6` and relative tolerance zero. See [reproduction_results.txt](evidence/reproduction_results.txt).

These checks demonstrate tested behaviour and consistency between implementations. They do not constitute an untouched final accuracy validation or exhaustive testing of all possible inputs.

After the source-documentation updates, a fresh clone at commit `47716c61643c558dbe519261ab3a073377c2366c` passed syntax compilation, all 13 repository unit tests, and the executable documentation examples in `reconstruct.py` and `models.py`. The commands and output are saved in the notebook, and the rerun is documented in `TEST_REPORT.md`. HTML documentation was then regenerated from that checked source.

## HTML source documentation

Generated documentation is stored in [docs/](docs/).

To view the formatted pages, download or clone the repository, then open `docs/index.html` in a browser. Keep all files in `docs/` together, including `search.js`. GitHub's normal file view may show HTML source instead of rendering the page.

The documentation was generated using pdoc 16.0.0. To regenerate it from the repository's main directory:

```bash
python -m pip install pdoc==16.0.0
```

Then run:

```bash
python -c "import os, subprocess, sys; env=os.environ.copy(); env['PYTHONPATH']=os.path.abspath('src'); subprocess.run([sys.executable, '-m', 'pdoc', '--docformat', 'numpy', '-o', 'docs', 'src/audit.py', 'src/reconstruct.py', 'src/models.py', 'src/evaluate.py', 'src/compare.py'], env=env, check=True)"
```

Regenerate the documentation after relevant source changes to keep it consistent with the code.

## Limitations and current status

- The comparison concerns one sensor, evaluated on a development segment and a later-period robustness segment. Results may not generalise to other sensors or buildings.
- Previously examined data must not be described as an untouched test set.
- Interpolation requires observations after the gap and therefore does not represent immediate real-time prediction.
- Regression requires temperature, humidity and pressure during the CO₂ outage.
- Artificially hidden readings may not represent all real sensor-failure patterns.
- The spline can introduce substantial curvature and overshoot across gaps.
- Agreement with hidden sensor measurements does not establish agreement with the true physical CO₂ concentration.
- The report discusses engineering usefulness and limitations. Application-specific acceptance criteria and validation on additional sensors remain future work.

The repository includes the completed method comparisons, numerical verification tests, reproduction evidence, runtime measurements, spline sensitivity analysis, later-period checks and HTML source documentation. The accompanying report explains the engineering interpretation, limitations and conclusions.

## AI assistance

ChatGPT was used to help draft code, design tests, explain methods, write documentation and guide the project workflow. Gemini in Google Colab was used to explain code, help fix errors and suggest code for additional graphs based on requested changes.

AI-assisted code was run and checked using synthetic reference answers, repository tests and comparisons with saved real-data results. Graphs and error tables were reviewed to assess method behaviour and limitations.

The accompanying report reflects on AI contributions, verification, decisions and learning. Responsibility for understanding and explaining the submitted work remains with the student.
## Licence

Repository code is provided under the [MIT licence](LICENSE). This licence does not grant rights to redistribute the original unit dataset.
