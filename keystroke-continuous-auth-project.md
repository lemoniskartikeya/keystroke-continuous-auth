# Keystroke Dynamics — Continuous Authentication System

## Project Overview
A behavioral biometrics system that continuously monitors your typing patterns (not passwords/content — only timing) and flags when someone other than you appears to be typing on your PC. Unlike traditional keystroke-auth projects that check identity once at login, this system monitors **continuously** during a session using free-text typing (any typing, not a fixed password).

**Why it's non-generic:** most keystroke dynamics projects use fixed-text typing (same password every time). Free-text continuous monitoring is a harder, less-solved research problem — this is the differentiator for a resume/research angle, and complements a cybersecurity + anomaly detection profile.

**Privacy-first design:** the system never logs actual typed content/words — only key-press/release timestamps (and optionally which key, for digraph timing), processed into features and discarded. This makes it ethically clean and closer to how commercial tools (e.g., TypingDNA) work.

---

## Core Idea
Train an anomaly detection model on your own typing timing patterns. If someone else starts typing, their timing behavior differs from your baseline — the system flags this as an anomaly and raises a warning (notification, or lock screen).

---

## Feature Engineering (Raw Keystrokes → ML Features)

Raw log format:
```
key: h   press: 0.000s   release: 0.090s
key: e   press: 0.150s   release: 0.230s
```

Per-key metrics:
- **Dwell time** = release − press (how long a key is held)
- **Flight time** = next key's press − previous key's release (gap between keys)

These raw per-key values are grouped into a **window** (e.g., 50 keystrokes), and aggregated into a feature vector:

| Feature | Example value |
|---|---|
| avg_dwell_time | 0.075s |
| std_dwell_time | 0.015s |
| avg_flight_time | 0.065s |
| std_flight_time | 0.020s |
| typing_speed (keys/sec) | 5.88 |
| backspace_rate | 0.04 |

Optional: per-digraph latency features (e.g., `avg_flight_th`, `avg_flight_he`) for your most frequent letter pairs — adds discriminative power.

Each window → one row of features → one input to the ML model.

---

## Model
- **Isolation Forest** or **One-Class SVM** (scikit-learn), trained only on your own "normal" feature vectors (anomaly detection framing, not classification, since impostor data isn't available upfront).
- Optional: collect small imposter samples (2-3 friends typing same text) to validate thresholds via ROC curve.
- Standard evaluation metrics from keystroke dynamics literature: **False Acceptance Rate (FAR)** and **False Rejection Rate (FRR)**.

---

## Sliding Window + Decision Logic

Two separate concepts combine here:

1. **Sliding window (feature generation):** windows overlap and slide forward (e.g., 50-keystroke windows advancing every 10 keystrokes) so a fresh anomaly score is produced frequently instead of waiting for a full new batch each time.

2. **Recent-scores buffer (decision smoothing):** the last N window scores (e.g., 5) are kept in a rolling buffer (`collections.deque(maxlen=5)`). An alert only fires if a majority (e.g., 3 out of 5) are anomalous — this avoids false alarms from a single unusual keystroke burst, while still catching sustained pattern shifts (an actual impostor).

```python
from collections import deque
recent_scores = deque(maxlen=5)
recent_scores.append(new_score)

anomalous_count = sum(1 for s in recent_scores if s > threshold)
if anomalous_count >= 3:
    trigger_alert()
```

---

## Build Roadmap

| Phase | Task | Notes |
|---|---|---|
| 1 | Data collection | `pynput` background listener, log only timestamps (+ key ID if doing digraphs). Collect 1500-2000+ keystrokes across varied sessions (morning/night, tired/alert). |
| 2 | Feature engineering | Convert raw logs into windowed feature vectors (pandas/numpy: mean, std, rate calculations). |
| 3 | Baseline model | Train Isolation Forest / One-Class SVM on your own data; validate on held-out 20% + small imposter samples. |
| 4 | Sliding window + scoring | Implement overlapping windows + rolling score buffer + alert threshold logic. |
| 5 | Real-time integration | Wrap as background service; trigger notification/lock on sustained anomaly. |
| 6 | Evaluation & write-up | Report FAR/FRR; test robustness against drift (different keyboard, time of day, fatigue). |

---

## System Integration (Windows)

1. **Continuous listener:** `pynput.keyboard.Listener` with `listener.join()` keeps the script running indefinitely.
2. **Auto-start on boot:**
   - Simple: place a shortcut/`.bat` file in `shell:startup`.
   - Reliable: Windows Task Scheduler, trigger = "At log on."
3. **Silent background run:** save script as `.pyw` to hide the console window.
4. **Alerting:** `plyer` / `win10toast` for system notifications; `ctypes.windll.user32.LockWorkStation()` for a hard lock on confirmed anomaly.
5. **Model persistence:** train once, `joblib.dump(model, 'model.pkl')`; background script only `joblib.load()`s it at startup — no retraining each run.
6. **Optional polish:** `pystray` for a system tray icon to show live status / toggle on-off — good for a resume demo.

---

## Tech Stack
`Python`, `pynput`, `scikit-learn`, `pandas`, `numpy`, `joblib`, `plyer`/`win10toast`, `pystray` (optional), `matplotlib` (for ROC curves in write-up).

---

## Research/Resume Value
- Frames as **continuous authentication** rather than one-shot login check — an active, real research area.
- Free-text (vs. fixed-text) keystroke dynamics is a genuinely open problem — good angle for an undergrad symposium paper or preprint.
- Complements existing cybersecurity/anomaly-detection research profile (NSL-KDD IDS, TESS anomaly detection) without duplicating either.
- Drift analysis (does typing pattern hold up over weeks, different keyboards) adds a research-grade evaluation angle beyond a typical class project.
