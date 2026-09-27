# Reconstructing missing indoor CO₂ sensor readings

## Engineering question
How accurately can short gaps in indoor CO₂ sensor measurements be reconstructed using numerical interpolation, and how does accuracy change as the missing interval gets longer?

Reliable CO₂ measurements help assess indoor air quality. This project investigates offline reconstruction of missing readings when measurements before and after a gap are available.

## Data
Source: MMA3001 Dataset 2, Monash Smart Infrastructure environmental sensor data.

The current analysis uses sensor `6012002000869` and CO₂ readings in parts per million (ppm). The original environmental sensor ZIP is kept outside this repository. Repeated records are identified using each measurement's timestamp; the audit found 29,341 CSV rows for this sensor but 13,800 distinct CO₂ timestamps.

## Methods and current progress
- `src/audit.py` checks repeated CO₂ records.
- `sensor_gap_exploration.ipynb` hides known readings, reconstructs them, and compares estimates with the hidden values.
- Baseline: repeat the last available CO₂ reading.
- Numerical method: linear interpolation between readings on either side of a gap.
- Error metric: mean absolute error (MAE), in ppm.

Preliminary comparisons of gaps containing 6, 18, and 36 hidden readings are in the notebook. These are exploratory results, not the final validation.

## How to run the exploration
Open `sensor_gap_exploration.ipynb` in Google Colab. Run its cells in order and upload the original environmental sensor ZIP when prompted. Do not upload the dataset ZIP to this public repository.

## Project status
Development is in progress. Final validation, tests, documentation, and engineering conclusions will be added as the project develops.
