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

- [Complete MAE, RMSE and gap-duration results](co2_position_cases/position_errors.csv)
- [Summary by position, gap size and method](co2_position_cases/position_summary.csv)
- [Best methods for each gap using MAE and RMSE](co2_position_cases/position_winners.csv)
- [Individual recorded CO₂ values and predictions](co2_position_cases/hidden_predictions.csv)
- [Dates and times of the ten selected windows](co2_position_cases/selected_windows.csv)
- [Excluded-gap record](co2_position_cases/excluded_gaps.csv)
- [Selection procedure, checks and limitations](co2_position_cases/selection_details.json)

To reproduce this experiment, run the notebook cells in order with the original environmental sensor ZIP. The final gap-position cell generates all result tables and 30 figures, then downloads `co2_position_cases.zip`. It displays three previews from Case 1. Four selected figures are included below.

### Selected case figures

These figures illustrate different outcomes. They were selected after reviewing the results, so they are examples rather than an unbiased sample for estimating overall performance. The complete result tables support the overall conclusions.

#### Case 1: gap position near hour 6

Linear has the lowest MAE for all three gap sizes. For the 36-reading gap, the recorded concentration generally decreases, and linear follows the overall change more closely than the constant previous-value estimate.

![Case 1: gaps near hour 6](co2_position_cases/case_01_hour_06.png)

#### Case 2: gap position near hour 6

The MAE winner changes with gap size: previous value for six readings, regression for 18 readings, and linear for 36 readings. In the 18-reading gap, the recorded values fall below both boundary concentrations, which limits the straight-line estimate. Regression is closer in this particular case, while the spline introduces an upward overshoot.

![Case 2: gaps near hour 6](co2_position_cases/case_02_hour_06.png)

#### Case 10: gap position near hour 12

Spline narrowly wins the six-reading gap by MAE: 3.54 ppm compared with linear's 3.63 ppm. Linear wins that gap by RMSE. The small difference and metric disagreement do not provide strong evidence that spline should be preferred. Linear has lower errors for the longer gaps in this figure.

![Case 10: gaps near hour 12](co2_position_cases/case_10_hour_12.png)

#### Case 7: gap position near hour 18

Previous value narrowly beats linear by MAE for the six-reading gap, while linear wins the longer gaps. For the 36-reading gap, the spline produces a large downward overshoot and an MAE of 137.42 ppm, compared with 9.26 ppm for linear. This shows why a smooth curve should not automatically be treated as an accurate reconstruction.

![Case 7: gaps near hour 18](co2_position_cases/case_07_hour_18.png)

### Verification and limitations

The workflow checks that gap/context indices remain inside the selected day, hidden indices are excluded from spline inputs, and predictions have the expected shape and finite values.

MAE and RMSE were recalculated from the individual predictions and matched the reported errors within absolute tolerance `1e-9`, with relative tolerance zero. The saved files contain 90 gap comparisons and 360 method results. These are evaluation cases, not additional repository unit tests.

Some simulated gaps overlap and should not be treated as statistically independent samples. The periods had already been examined, so this is an additional case comparison rather than an untouched final test.

The results support linear interpolation overall while showing exceptions for individual gaps. They do not establish a reliable rule for choosing a method from gap position alone, generalisation to other sensors, or agreement with the true physical CO₂ concentration.
