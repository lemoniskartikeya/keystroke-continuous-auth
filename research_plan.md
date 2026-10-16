# Research Roadmap & Methodology: Continuous Keystroke Biometrics
> **Project**: Privacy-Preserving Free-Text Continuous Authentication  
> **Phase**: Phase 6 — Empirical Evaluation, Multi-Subject Benchmarking, Drift Analysis, and Academic Manuscript  
> **Author**: Kartikeya  
> **Status**: In Progress  

---

## 1. Executive Summary & Research Charter

### 1.1 The Scientific Problem
Most keystroke dynamics research and commercial authentication products (e.g., typing-based 2FA) operate in a **fixed-text** paradigm: the user types a predefined string (such as a passphrase or username) repeatedly. In contrast, this project tackles **free-text continuous authentication**:
- The user types arbitrary, unconstrained natural language across any desktop application.
- The system continuously evaluates identity in the background during active desktop sessions.
- Identity verification is formulated as **one-class anomaly detection** (learning exclusively the authorized user's manifold), addressing the realistic threat model where negative/impostor samples cannot be known at training time.

### 1.2 Transition from Engineering to Research
Phases 1 through 5 established a functioning end-to-end prototype:
- **Phase 1**: Hardware timing capture without keystroke content logging.
- **Phase 2**: 9-dimensional statistical feature extraction over sliding windows.
- **Phase 3**: Isolation Forest anomaly scoring yielding an Equal Error Rate (EER) of **10.9%** at threshold $-0.0518$.
- **Phase 4**: Majority-vote consensus buffer ($8/10$) eliminating false lockouts ($0.0\%$ session FAR).
- **Phase 5**: Dynamic Ramp-Up buffer ($3/3 \to 4/5 \to 8/10$) cutting detection latency by 42% (~70 keystrokes / ~14 words) and an idle-timeout watchdog for unattended workstation takeovers.

To transition this from a functional project into a **publishable paper** (e.g., IEEE S&P / USENIX Security workshop, ACM CCS workshop, IEEE Access, or an undergraduate research symposium / arXiv preprint), we must replace ad-hoc observations with **formal hypotheses, multi-impostor benchmarking, ablation studies, statistical confidence intervals, temporal drift modeling, and threat boundary analysis**.

---

## 2. Core Research Questions (RQs) & Hypotheses

An academic paper is structured around answering concrete scientific questions. We establish six core Research Questions:

### RQ1: Privacy-Preserving Biomechanical Separability & Feature Ablation
* **Question**: *Can privacy-preserving, non-semantic timing statistics (specifically spacebar dwell and negative flight rollover) achieve discriminative power comparable to full-text or digraph-logging models without persisting readable user text?*
* **Hypothesis**: The spacebar hold time ($d \approx 2.4$) and key rollover rate ($d \approx 1.0$) represent subconscious biomechanical habits reflecting motor control and word-boundary rhythm. Incorporating them will drop the EER by $\ge 15$ percentage points compared to classical dwell/flight baselines.
* **Why this matters to reviewers**: Privacy compliance (GDPR, HIPAA) prevents deploying keyloggers in enterprise environments. Demonstrating high biometric fidelity without logging characters or retaining full digraph dictionaries is a strong privacy contribution.

### RQ2: Multi-Impostor Generalization Across Typing Typologies
* **Question**: *Does a model trained exclusively on one authorized user successfully reject diverse impostor profiles (fast touch typists, slow hunt-and-peck typists, erratic backspace-heavy typists), or does detection collapse when the impostor's speed matches the genuine user?*
* **Hypothesis**: Because the feature space decouples raw speed from fine-grained motor traits (dwell distribution, key rollover depth, spacebar cadence), the system maintains $\text{FAR} < 15\%$ across diverse impostor typologies, even when an impostor types at an identical overall words-per-minute (WPM) rate.
* **Why this matters to reviewers**: Evaluating against only *one* impostor (the current friend dataset) is the single biggest empirical vulnerability in amateur biometrics papers. A reviewer will ask: *"What if your friend was just typing faster than you?"* Proving robustness across multiple distinct impostor profiles proves true biometric individuality.

### RQ3: The Cold-Start vs. False-Alarm Latency Tradeoff
* **Question**: *How can continuous authentication systems overcome the cold-start delay required to reach statistical consensus without inflating false rejections on the genuine user?*
* **Hypothesis**: A sub-linear Dynamic Ramp-Up consensus schedule ($3/3 \to 4/5 \to 8/10$) significantly reduces Mean Time to Detect (MTTD) on impostors while maintaining a zero False Rejection Rate ($FRR = 0.0\%$) during initial typing bursts.
* **Why this matters to reviewers**: Prior work typically uses static window buffers that either trigger rapid false alarms on momentary hesitation or take 25–40 words to react, during which an intruder can exfiltrate data. Quantifying the dynamic schedule solves a core systems-security dilemma.

### RQ4: State Watchdog & Buffer Contamination during Takeover
* **Question**: *What is the impact of session-boundary contamination during an unattended desk takeover, and does an inactivity watchdog provably restore fast intruder detection?*
* **Hypothesis**: In the absence of an idle flush, cross-user feature blending inflates detection latency by $\ge 15\%$. Flushing the sliding FIFO buffer upon an idle threshold (e.g., $\tau_{idle} = 30\text{s}$) decouples user distributions and forces intruders directly into early dynamic consensus.
* **Why this matters to reviewers**: Most behavioral biometrics papers concatenate synthetic attack traces end-to-end without modeling idle transitions, ignoring real-world buffer pollution.

### RQ5: Temporal Baseline Drift & Within-Subject Stability
* **Question**: *How does a genuine user's typing rhythm evolve across time, diurnal cycles (morning vs. night), and physical fatigue, and can an adaptive baseline prevent False Rejection creep?*
* **Hypothesis**: Natural typing speed and flight variance exhibit measurable temporal drift over multi-hour intervals. An Exponential Moving Average (EMA) baseline update rule or adaptive threshold margin stabilizes FRR over extended sessions without compromising security.
* **Why this matters to reviewers**: "Model drift" is the #1 objection reviewers raise against behavioral biometrics. Addressing drift elevates the work from a toy project to a robust longitudinal study.

### RQ6: Adversarial Evasion & Security Boundaries
* **Question**: *What are the mathematical and operational limits of continuous keystroke dynamics against deliberate adversarial evasion (e.g., mimicry, low-and-slow micro-bursts, or scripted injection)?*
* **Hypothesis**: Continuous free-text biometrics is fundamentally a Layer 3 defense-in-depth control. Attackers typing under $\sim 70$ keys cannot be reliably caught by statistical distribution moments without unacceptable false alarm rates, defining a clear operational boundary for complementary controls (EDR, OS privilege elevation).
* **Why this matters to reviewers**: Honest, rigorous boundary analysis earns significant academic respect over unverified claims of "unhackable" biometrics.

---

## 3. The Multi-Impostor & Multi-Session Challenge (Why It Matters & What To Do)

### 3.1 The Single-Impostor Problem
Currently, the repository contains:
- `data/keystroke_log_genuine.csv`: 10,280 keystrokes from the authorized user.
- `data/keystroke_log_anomalous.csv`: 10,170 keystrokes from **one** friend/impostor.

While this verified that the pipeline works end-to-end, evaluating against only a single impostor is a recognized limitation in biometrics research. If the friend happened to have a significantly higher or lower WPM than the authorized user, an Isolation Forest could separate them purely on typing speed rather than fine-grained biomechanics.

### 3.2 The Solution: Multi-Impostor Benchmarking (3 Approaches)

To provide rock-solid empirical validation, we employ a three-tier multi-impostor strategy:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   MULTI-IMPOSTOR BENCHMARKING STRATEGY                 │
└────────────────────────────────────────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼──────────────────────────────┐
    ▼                               ▼                              ▼
[Tier 1: Behavioral             [Tier 2: Multi-Friend          [Tier 3: Public Benchmark
 Typology Stratification]        Collection Protocol]           Dataset Integration]
• Fast Touch Typist             • Impostor 2: Slow/Cautious    • Clarkson II Benchmark
• Hesitant Hunt-and-Peck        • Impostor 3: Average Cadence   • Buffalo Free-Text Dataset
• Cadence-Matched Impostor      • Hardware: Different Keyboards • 20+ real unconstrained
  (Speed normalized to user)    • Collected via Script 01         typists cross-evaluated
```

#### Approach 1: Behavioral Typology Stratification (Synthetic & Segmented)
- **What to do**: Slice and perturb anomalous typing into distinct behavioral typologies:
  1. **Speed-Matched Adversary**: Normalize the impostor's flight and dwell distributions to match the genuine user's exact median speed, forcing the model to rely *strictly* on subconscious biomechanical markers (space dwell, overlap rate, flight variance).
  2. **Bursty / Hesitant Typist**: Low typing speed, high flight standard deviation, low overlap rate.
  3. **High-Rollover Fluid Typist**: High typing speed, high negative flight rate, short dwell times.
- **Why**: Proves that detection is driven by biomechanical motor control rather than trivial typing speed differences.

#### Approach 2: Real Multi-Subject Data Collection (`src/01_keystroke_collector.py`)
- **What to do**: Have 2–3 different individuals type 1,000–1,500 keystrokes using [`src/01_keystroke_collector.py`](file:///C:/type/src/01_keystroke_collector.py):
  - Save as `data/impostor_subject_2.csv`, `data/impostor_subject_3.csv`.
- **Why**: Provides genuine human empirical diversity across different hand sizes, motor skills, and typing habits.

#### Approach 3: Public Benchmark Dataset Integration (Clarkson II / Buffalo)
- **What to do**: Download an open, standard free-text keystroke research benchmark (e.g., the Buffalo Free-Text Keystroke Dataset or Clarkson University II Keystroke Dataset), extract our 9-feature vectors, and benchmark our `ContinuousAuthDecisionEngine` against 10–20 independent subjects.
- **Why**: Compares our methodology directly against state-of-the-art academic baselines published in IEEE/ACM literature.

---

### 3.3 Multi-Session Genuine Data (Evaluating Real Temporal Drift)

#### Why It Matters
A user's typing pattern changes based on:
1. **Circadian Rhythm / Fatigue**: Alert in the morning vs. exhausted at midnight.
2. **Cognitive Load**: Transcribing prose vs. writing complex code with punctuation and brackets.
3. **Physical Hardware**: Built-in laptop membrane keyboard vs. external mechanical keyboard with mechanical travel.

If a model trained on a morning session rejects the user late at night, the False Rejection Rate (FRR) becomes unacceptable.

#### What To Do
1. **Multi-Session Collection Protocol**:
   - Log 3 separate genuine sessions:
     - `session_morning_fresh.csv` (~3,000 keys)
     - `session_night_fatigued.csv` (~3,000 keys)
     - `session_coding_symbols.csv` (~3,000 keys)
2. **Longitudinal Cross-Validation**:
   - Train the model exclusively on the baseline session.
   - Evaluate FRR on the other sessions.
3. **Adaptive Baseline (Exponential Moving Average — EMA)**:
   - When a session is verified genuine ($S(x) \ge \tau_{safe}$), slowly update the running feature mean and variance:
     $$\mu_{t} = (1 - \alpha) \mu_{t-1} + \alpha x_t$$
   - Evaluate whether this keeps FRR $< 1.0\%$ indefinitely across days.

---

## 4. Sparse Digraph (Bigram) Latency Analysis

### 4.1 What Was Discussed Earlier
In `feature_candidates.md`, top digraphs (`flight_re`, `flight_th`, `flight_er`, `flight_st`, `flight_in`) showed massive separation ($d > 0.8$).

### 4.2 The Free-Text Sparsity Problem
- In **fixed-text** (passwords), digraphs appear every single trial (e.g., `p-a-s-s-w-o-r-d`).
- In **free-text**, in a short window of 50 keystrokes, the specific bigram `th` might appear twice or zero times. If a feature vector expects `flight_th`, but the user typed 50 characters without typing "th", the value is `NaN`.

### 4.3 What To Do in the Research
- We will include an explicit **Digraph Feasibility Analysis** in the research notebook and paper:
  - Measure digraph frequency in unconstrained text.
  - Test imputation vs. sparse feature handling.
  - Demonstrate why **global biomechanical features** (`avg_space_dwells`, `overlap_rate`) are statistically superior to sparse digraphs for **short-latency** ($W=50$) continuous monitoring. This is a novel analytical insight that reviewers will appreciate.

---

## 5. Desktop System Integration & Live Demonstration (Track 2)

### 5.1 Why This Still Matters for Research
An academic paper or symposium presentation is exponentially more convincing when accompanied by a live, working artifact. Reviewers and committee members love to test the system live.

### 5.2 What To Build
1. **System Tray Daemon (`src/05_tray_monitor.py`)**:
   - Built on `pystray`.
   - Displays a dynamic icon that changes color in real-time:
     - 🟢 **Green**: Authenticated genuine session.
     - 🟡 **Yellow**: Buffer warming up / Dynamic Ramp-Up stage.
     - 🔴 **Red**: Anomaly detected / Impostor alert state.
   - Tray menu options: *Pause Monitoring*, *View Session Metrics*, *Toggle Auto-Lock Workstation*, *Export Session Log*.
2. **Native Toast Warning (`win10toast` / `plyer`)**:
   - Pops a native Windows toast notification before locking: *"Continuous Biometrics: Unauthorized typing rhythm detected. Workstation will lock in 5 seconds."*

---

## 6. Experimental Program (Phase 6 Methodology)

The research program is structured into five concrete experiments documented in `notebooks/06_research_evaluation_and_drift.ipynb`:

```
┌────────────────────────────────────────────────────────────────────────┐
│               PHASE 6 EXPERIMENTAL PROGRAM (NOTEBOOK 06)              │
└────────────────────────────────────────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼──────────────────────────────┐
    ▼                               ▼                              ▼
[Experiment 1]               [Experiment 2]                 [Experiment 3]
Feature Ablation &           Statistical Rigor:             Multi-Impostor &
Distribution Separability    Bootstrap 95% CIs              Typology Benchmark
• Baseline (4 feat)          • 1,000 bootstrap resamples    • Genuine vs Impostor 1
• + Speed & Cadence (6 feat) • EER ± 95% CI                 • Speed-matched Impostor
• + Space Dwell & Overlap    • FAR / FRR ± 95% CI           • Bursty/Erratic Impostor
• Full 9-feature model       • Detection Latency bounds     • Multi-Subject Summary
    │                               │                              │
    └───────────────────────────────┼──────────────────────────────┘
                                    │
    ┌───────────────────────────────┴──────────────────────────────┐
    ▼                                                              ▼
[Experiment 4]                                             [Experiment 5]
Temporal Drift &                                           Sparse Digraph
Adaptive Baseline                                          Feasibility Analysis
• Chronological block splitting                            • Frequency of top bigrams
• Kolmogorov-Smirnov drift test                            • Missing value sparsity in W=50
• EMA online feature update rule                           • Global vs local feature trade-off
• FRR stability comparison
```

---

### Detailed Experiment Specifications

#### Experiment 1: Systematic Feature Ablation Study
* **Goal**: Measure the exact marginal value of each feature group to prove RQ1.
* **Configurations**:
  1. **Config A (Classical Baseline — 4 Features)**: `avg_dwell`, `std_dwell`, `avg_flight`, `std_flight`.
  2. **Config B (+ Typing Cadence — 6 Features)**: Config A + `typing_speed`, `backspace_rate`.
  3. **Config C (+ Biomechanical Rollover — 8 Features)**: Config B + `avg_space_dwells`, `overlap_rate`.
  4. **Config D (Full Proposed Pipeline — 9 Features)**: Config C + `long_pause_rate`.
* **Deliverables**:
  - Overlaid ROC Curves ($\text{FAR}$ vs. $\text{FRR}$) for all 4 configurations.
  - Ablation comparison table reporting: **EER**, **AUC-ROC**, **Threshold at EER**, and **Cohen's $d$ ranking**.

#### Experiment 2: Statistical Rigor & Bootstrap Confidence Intervals
* **Goal**: Compute empirical variance and confidence bounds to satisfy peer-review standards.
* **Method**:
  - Bootstrap resampling with replacement ($B = 1,000$ iterations) over test windows.
  - Compute 95% Confidence Intervals for:
    $$\text{EER} \in [\text{EER}_{2.5\%}, \text{EER}_{97.5\%}]$$
    $$\text{AUC} \in [\text{AUC}_{2.5\%}, \text{AUC}_{97.5\%}]$$
    $$\text{Detection Latency (keys)} \in [\text{Latency}_{2.5\%}, \text{Latency}_{97.5\%}]$$
* **Deliverables**:
  - Distribution histograms of bootstrapped EER and AUC.
  - Formal summary table with mean $\pm$ standard error and 95% CI.

#### Experiment 3: Multi-Impostor & Typology Robustness
* **Goal**: Test RQ2 to prove the model is not relying on trivial speed differences.
* **Method**:
  - Evaluate the model against:
    1. Raw Impostor 1 (`data/keystroke_log_anomalous.csv`).
    2. Speed-Normalized Impostor (synthetic adjustment matching genuine user mean flight/dwell).
    3. Hesitant / Bursty Impostor (stratified high-pause subsets).
* **Deliverables**:
  - Comparative FAR / Detection Latency table across impostor typologies.
  - Evidence that fine-grained motor traits maintain separation when speed is controlled.

#### Experiment 4: Longitudinal Drift & Adaptive Baseline Updating
* **Goal**: Answer RQ5 by simulating multi-session drift and testing adaptive defense.
* **Method**:
  - Chronological chunking of genuine sessions.
  - KS-test drift metrics per feature.
  - Implementation of EMA online baseline update:
    $$\mu_{t} = (1 - \alpha) \mu_{t-1} + \alpha x_t$$
* **Deliverables**:
  - Drift degradation plot (Static model FRR vs. Adaptive model FRR over time).
  - Feature drift stability ranking.

#### Experiment 5: Sparse Digraph Feasibility Analysis
* **Goal**: Clarify why global features outshine sparse digraphs in short-window free-text.
* **Method**:
  - Quantify occurrence frequency of `re`, `er`, `th`, `st`, `in` across 50-keystroke windows.
  - Compute sparsity percentage (% of windows with missing digraph values).
* **Deliverables**:
  - Sparsity analysis table justifying the selection of space dwell and overlap rate over bigram dictionaries.

---

## 7. Academic Paper Structure (`paper/`)

To prepare for conference/preprint submission, we will structure the paper following IEEE/ACM formatting guidelines:

| Section | Title | Target Content |
|---|---|---|
| **Title** | *Continuous Behavioral Biometrics via Privacy-Preserving Keystroke Dynamics and Dynamic Consensus* | Technical, descriptive title |
| **Abstract** | ~250 words | Problem, key insights, EER result (10.9%), latency reduction (42%), zero false lockout guarantee, multi-impostor robustness. |
| **I** | **Introduction** | Traditional login vs. continuous auth; threat model of unlocked workstations; core contributions. |
| **II** | **Related Work** | Fixed-text vs. free-text keystroke dynamics; deep learning vs. classical one-class anomaly detection; privacy-preserving biometrics. |
| **III** | **Threat Model & Security Boundaries** | Physical insider takeover, remote session hijacking; out-of-scope threats (rapid drive-by injection, replay); defense-in-depth placement. |
| **IV** | **Privacy-Preserving Feature Architecture** | Timing capture pipeline; 9-feature extraction; space dwell & overlap formulations; digraph sparsity trade-off. |
| **V** | **Dynamic Consensus & State Watchdogs** | Mathematical formulation of Dynamic Ramp-Up ($3/3 \to 4/5 \to 8/10$); state machine; Inactivity Watchdog buffer flush. |
| **VI** | **Experimental Evaluation & Ablation** | Dataset details; Feature ablation study; ROC/EER curves; 95% bootstrap confidence intervals; detection latency benchmarks. |
| **VII** | **Multi-Impostor & Typology Robustness** | Performance across diverse impostor typologies; speed-normalized adversary evaluation. |
| **VIII** | **Temporal Drift & Adaptive Defense** | Longitudinal stability analysis; Kolmogorov-Smirnov drift tests; EMA adaptive baseline results. |
| **IX** | **Discussion & Limitations** | Single-modality limitations; cold-start minimum latency; adversarial counter-measures. |
| **X** | **Conclusion** | Summary of findings and future research directions (multi-modal keyboard + mouse fusion). |

---

## 8. Complete Execution Checklist

```
[Phase 6.1] Master Research Roadmap & Methodology (research_plan.md)
   ├── Define 6 Core Research Questions (RQs)
   ├── Multi-impostor benchmarking strategy
   ├── Multi-session drift & adaptive baseline
   ├── Sparse digraph feasibility framing
   └── System tray & notification demo artifact

[Phase 6.2] Comprehensive Research Notebook (notebooks/06_research_evaluation_and_drift.ipynb)
   ├── Exp 1: Feature Ablation Study (4 configs: 4-feat, 6-feat, 8-feat, 9-feat)
   ├── Exp 2: 95% Bootstrap Confidence Intervals (1,000 iterations for EER/AUC/Latency)
   ├── Exp 3: Multi-Impostor & Typology Robustness (Speed-normalized & stratified profiles)
   ├── Exp 4: Longitudinal Drift Analysis & EMA Adaptive Baseline
   └── Exp 5: Sparse Digraph Feasibility Evaluation

[Phase 6.3] Publication Visualizations & Tables (saved to results/)
   ├── results/feature_ablation_roc.png
   ├── results/bootstrap_eer_distribution.png
   ├── results/multi_impostor_latency_comparison.png
   └── results/temporal_drift_stability.png

[Phase 6.4] Formal Academic Paper Manuscript (paper/)
   ├── paper/paper_draft.md (or LaTeX IEEEtran template)
   └── Full empirical tables, mathematical proofs, and security boundary analysis

[Phase 6.5] Live Demonstration & Desktop Tray Utility (src/)
   ├── src/05_tray_monitor.py (pystray UI with live green/yellow/red icon)
   └── Native Windows Toast alert integration
```
