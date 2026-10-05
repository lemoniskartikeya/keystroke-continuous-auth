# Keystroke Continuous Authentication

A behavioral biometrics system that continuously verifies user identity based on free-text typing patterns. Unlike traditional password-based authentication, which verifies identity only at login, this system monitors typing behavior throughout an active session and raises an alert if the observed pattern deviates significantly from the authorized user's established baseline.

## Motivation

Most keystroke dynamics research and commercial systems (e.g., typing-based multi-factor authentication) rely on fixed-text input, where the user types the same string (such as a password) repeatedly. This project instead addresses **free-text continuous authentication**, a harder and comparatively less-explored problem, where typing behavior is monitored across arbitrary, unconstrained text rather than a fixed phrase.

This system is designed to complement, not replace, traditional authentication. It targets a different threat model: verifying that the person actively using a device after login is still the authorized user, rather than authenticating identity at a single point of entry.

## Privacy Design

The system captures only keystroke timing metadata: key-press and key-release timestamps. No sequences of typed content are persisted as readable text; timing data is processed into statistical features and the raw log is not used to reconstruct what was typed.

## How It Works

1. A background listener records key-press and key-release timestamps for each keystroke.
2. Raw timestamps are converted into two core timing metrics per key: dwell time (how long a key is held) and flight time (the gap between consecutive keys).
3. These metrics are aggregated over sliding windows of keystrokes into a fixed-length feature vector (average/standard deviation of dwell and flight time, typing speed, backspace rate).
4. An Isolation Forest model, trained exclusively on the authorized user's own baseline data, learns the shape of "normal" typing behavior.
5. Incoming windows are scored for anomaly. A sustained pattern of anomalous scores across multiple consecutive windows, rather than a single flagged window, triggers an alert, reducing false positives from momentary variation.

## Project Status

This project is under active development. Current progress:

- **Phase 1, Data Collection**: Complete. A background keystroke listener (`01_keystroke_collector.py`) logs press/release timestamps to CSV, with no raw content persisted beyond individual key identity needed for timing calculations.
- **Phase 2, Feature Engineering**: Complete. A feature extraction pipeline (`02_feature_extraction.ipynb`) converts raw keystroke logs into windowed feature vectors (dwell time, flight time, typing speed, backspace rate) using a sliding-window approach.
- **Phase 3, Model Training & Evaluation**: Complete. Isolation Forest trained on genuine baseline data (`03_model_training.ipynb`), evaluated using FAR/FRR curves and EER analysis. Current best result: **EER = 10.9%**.
- **Phase 4, Decision Logic**: Planned. Sliding-window anomaly scoring with majority-vote smoothing to reduce false alarms.
- **Phase 5, Real-Time Integration**: Planned. Background service with system notifications and lock-screen triggering on sustained anomaly detection.
- **Phase 6, Evaluation & Write-Up**: Planned. Drift analysis across multiple sessions/days and a research write-up intended for an arXiv preprint or undergraduate research symposium submission.

## Repository Structure

```
.
├── src/
│   └── 01_keystroke_collector.py    # Phase 1: keystroke timing data collector
├── notebooks/
│   ├── 02_feature_extraction.ipynb  # Phase 2: raw log to windowed feature vectors
│   └── 03_model_training.ipynb      # Phase 3: Isolation Forest training & EER evaluation
├── data/
│   └── keystroke_log_genuine.csv    # Baseline keystroke data (authorized user)
├── results/
│   └── far_frr_curve.png            # FAR/FRR curve with EER = 10.9% marked
├── .gitignore
└── README.md
```

## Requirements

- Python 3.10+
- pynput
- pandas
- numpy
- scikit-learn
- matplotlib
- joblib

Install dependencies:
```
pip install pynput pandas numpy scikit-learn matplotlib joblib
```

## Usage

### 1. Collect keystroke data
```
python src/01_keystroke_collector.py
```
Type naturally during the session. Press ESC to stop and save the log to CSV.

### 2. Extract features
Open and run `notebooks/02_feature_extraction.ipynb`. It converts the raw keystroke log into a windowed feature table, saved as a CSV ready for model training.

### 3. Train the model & evaluate
Open and run `notebooks/03_model_training.ipynb`. It trains an Isolation Forest on the genuine baseline data, plots FAR/FRR curves, and reports the Equal Error Rate (EER). Current best result: **10.9% EER**.

Subsequent phases (real-time integration, multi-session drift analysis) will be documented here as they are implemented.

## Results

![FAR/FRR Curve](results/far_frr_curve.png)

The FAR/FRR curve above shows the trade-off between False Acceptance Rate and False Rejection Rate across anomaly score thresholds. The model achieves an **Equal Error Rate (EER) of 10.9%**, meaning at the optimal threshold, roughly 1 in 9 unauthorized sessions would be accepted and 1 in 9 genuine sessions would be rejected.

## Evaluation Methodology

Model performance is assessed using standard keystroke dynamics evaluation metrics:

- **False Acceptance Rate (FAR)**: the rate at which an unauthorized user's typing is incorrectly accepted as the authorized user.
- **False Rejection Rate (FRR)**: the rate at which the authorized user's own typing is incorrectly flagged as anomalous.
- **Equal Error Rate (EER)**: the point at which FAR and FRR are approximately equal, used as a single summary metric for comparison against prior work.

## Limitations

- The system does not defend against snoop-forge-replay attacks, where an adversary with access to timing data from a prior session could attempt to reproduce the authorized user's typing rhythm.
- Model accuracy depends heavily on the diversity of the baseline data collected. A baseline captured under narrow conditions (e.g., a single session, consistent mood/time of day) may not generalize well to natural variation in the authorized user's own typing over time.
- This project uses classical machine learning methods (Isolation Forest) rather than deep learning approaches, by design, to keep the system lightweight and interpretable.

## Research Context

This project is being developed with the goal of contributing a research write-up on free-text continuous authentication, focusing on sliding-window decision smoothing and multi-day robustness/drift analysis using classical anomaly detection methods.

## License

To be determined.
