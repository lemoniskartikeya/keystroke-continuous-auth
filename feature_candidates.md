# Feature Engineering Candidates — Keystroke Authentication
> Based on statistical analysis of **7,024 genuine** and **5,374 impostor** raw keystrokes across **694 genuine** and **532 impostor** windows.
> **Current EER: 26.3%** (4 active features: `avg_dwell`, `std_dwell`, `avg_flight`, `std_flight`)

---

## How to Read This Document

- **Cohen's d** — measures how well-separated two distributions are. `d > 0.8` = large effect (strong separator). `d < 0.2` = weak/useless.
- **EER** (Equal Error Rate) — where FAR and FRR cross. **Lower is better**. 0% = perfect, 50% = random.
- **EER reduction estimates** are based on Cohen's d comparisons and separation between genuine/impostor distributions in *this* dataset.

---

## Currently Active Features (Baseline)

| Feature | Genuine Mean | Impostor Mean | Cohen's d | Notes |
|---|---|---|---|---|
| `avg_dwell` | 0.1108s | 0.0853s | **1.87** | Excellent — best current feature |
| `avg_flight` | 0.1701s | 0.1077s | **1.22** | Excellent |
| `std_flight` | 0.2231s | 0.1255s | **1.10** | Excellent |
| `std_dwell` | 0.0689s | 0.0318s | **0.91** | Good |

> `typing_speed` (d=1.05) and `backspace_rate` (d=0.26) are currently excluded from the model despite being extracted.
> **`typing_speed` should be re-added** — it was likely dropped from an earlier smaller dataset where the d was low.

---

## Recommended New Features

---

### TIER 1 — High Priority (Add These First)

---

#### 1. `avg_space_dwell` — Spacebar Hold Time

| Metric | Genuine | Impostor |
|---|---|---|
| Mean | **0.1303s** | **0.0710s** |
| Std | 0.0294s | 0.0159s |
| Count | 835 events | 853 events |

**Why it works:** Spacebar is pressed after every word. The genuine user holds space nearly **2× longer** than the impostor. This is a deep biomechanical habit reflecting word-boundary rhythm and is very hard to consciously mimic.

**How to compute:**
```python
space_mask = window["key_id"] == "Key.space"
"avg_space_dwell": window.loc[space_mask, "dwell"].mean()
```

**Estimated EER reduction: ~3–5 percentage points**
Rationale: The raw separation (0.0593s gap vs pooled std ~0.025s) implies a Cohen's d of ~2.4 — stronger than any current feature.

---

#### 2. `overlap_rate` — Key Rollover / Overlap Rate

| Metric | Genuine | Impostor |
|---|---|---|
| Overlap rate | **26.4%** | **17.9%** |
| Avg overlap depth | -0.047s | -0.036s |

**Why it works:** "Overlap" means the next key is pressed *before* the previous key is released (negative flight time). This is a hard-to-control biomechanical trait — it captures rollover habits that differ significantly between users.

**How to compute:**
```python
valid_flights = window["flight"].dropna()
"overlap_rate": (valid_flights < 0).mean()
```

**Estimated EER reduction: ~2–4 percentage points**
Rationale: 8.5 percentage point difference in overlap rate is strongly personal and independent from existing dwell/flight features.

---

#### 3. Re-enable `typing_speed`

| Metric | Genuine | Impostor | Cohen's d |
|---|---|---|---|
| Mean | 3.55 keys/s | 5.65 keys/s | **1.05** |

**Why it was dropped:** Appears to have been assessed on an earlier smaller dataset where the separation was low. On the full dataset it is a large-effect feature.

**Estimated EER reduction: ~2–3 percentage points** when re-added to the model.

---

#### 4. Digraph (Bigram) Latency — `flight_re`, `flight_th`, `flight_er`, `flight_st`, `flight_in`

Top performing digraphs by separation in this dataset:

| Digraph | G_count | I_count | Genuine flight | Impostor flight | Diff |
|---|---|---|---|---|---|
| `re` | 54 | 43 | 0.0952s | **-0.0335s** | **0.129s** |
| `er` | 69 | 79 | 0.0666s | **-0.0128s** | **0.079s** |
| `th` | 74 | 78 | 0.0273s | 0.1017s | 0.074s |
| `st` | 76 | 68 | 0.0825s | 0.0079s | 0.075s |
| `in` | 66 | 52 | 0.1190s | 0.0448s | 0.074s |

> Negative flight for `re` and `er` means the impostor presses the next key **before** releasing the previous one for those pairs — a completely different rollover pattern than the genuine user.

**Important caveat:** Digraphs appear only ~0.08–0.11 times per 50-keystroke window on average. Compute these as **session-level or large-window features** (200+ keystrokes), not per 50-keystroke window, to avoid NaN-heavy feature vectors.

**How to compute (session level):**
```python
for pair in ['re', 'er', 'th', 'st', 'in']:
    mask = (df["key_id"] == pair[0]) & (df["key_id"].shift(-1) == pair[1])
    flight_val = df.loc[mask, "flight"].dropna().mean()
    features[f"flight_{pair}"] = flight_val if not np.isnan(flight_val) else 0.0
```

**Estimated EER reduction: ~2–4 percentage points** (combined for top 3–4 digraphs)

---

### TIER 2 — Medium Priority

---

#### 5. `long_pause_rate` — Fraction of flight times > 0.5s

| Metric | Genuine | Impostor |
|---|---|---|
| Long pause rate | **7.37%** | **2.22%** |

**Why it works:** The genuine user pauses to think **3.3× more frequently** between keystrokes. This captures natural cognitive rhythm breaks that are hard to mimic.

```python
valid_flights = window["flight"].dropna()
positive_flights = valid_flights[(valid_flights >= 0) & (valid_flights < 2.0)]
"long_pause_rate": (positive_flights > 0.5).mean()
```

**Estimated EER reduction: ~1–2 percentage points**

---

#### 6. `dwell_cv` — Coefficient of Variation of Dwell Time

| Metric | Genuine | Impostor |
|---|---|---|
| Dwell CV | **0.79** | **0.46** |

**Why it works:** CV = std/mean normalizes variability by scale. The genuine user is 72% more variable *relative to their own mean*, independent of how fast they type. This is a different signal from `std_dwell`.

```python
"dwell_cv": window["dwell"].std() / window["dwell"].mean()
```

**Estimated EER reduction: ~1–2 percentage points**

---

#### 7. `post_space_flight` — Average flight time after spacebar

| Metric | Genuine | Impostor |
|---|---|---|
| Post-space mean | **0.2702s** | **0.1465s** |

**Why it works:** How long the genuine user takes to start typing the next word after hitting space — nearly 2× longer. Complements `avg_space_dwell` and captures inter-word rhythm.

```python
space_mask = window["key_id"] == "Key.space"
post_space = window.loc[space_mask, "flight"].dropna()
post_space = post_space[(post_space >= 0) & (post_space < 2.0)]
"post_space_flight": post_space.mean() if len(post_space) > 0 else 0.0
```

**Estimated EER reduction: ~1–2 percentage points** (partially correlated with `avg_space_dwell`)

---

#### 8. `burst_rate` — Fraction of very fast keypresses (flight < 0.05s)

| Metric | Genuine | Impostor |
|---|---|---|
| Burst rate | **26.1%** | **36.7%** |

**Why it works:** The impostor bursts 40% more than the genuine user. Captures rhythmic patterns in fast typing that complement the overlap rate.

```python
valid_flights = window["flight"].dropna()
positive_flights = valid_flights[valid_flights >= 0]
"burst_rate": (positive_flights < 0.05).mean()
```

**Estimated EER reduction: ~1 percentage point**

---

### TIER 3 — Skip / Low Priority

| Feature | Reason to Skip |
|---|---|
| `backspace_rate` | d=0.26 — weak separator even on full dataset |
| `trigraphs` | Only 1 trigraph (`the`) has ≥20 occurrences in both sets — far too sparse |
| `special_key_rate` | Closely correlated with backspace_rate |
| `dwell_entropy` | High complexity, overlaps with `dwell_cv` signal |
| `p25/p75 dwell percentiles` | Overlaps with std_dwell + median; not worth the extra dimensions |

---

## Summary Table

| Feature | Cohen's d | Implementation | Est. EER Reduction |
|---|---|---|---|
| `avg_space_dwell` | ~2.4 | Easy | **3–5%** |
| Re-enable `typing_speed` | 1.05 | Trivial | **2–3%** |
| `overlap_rate` | ~1.3 | Easy | **2–4%** |
| Digraphs (`re`, `er`, `th`, `st`) | ~1.2 per pair | Medium | **2–4%** (combined) |
| `long_pause_rate` | ~0.9 | Easy | **1–2%** |
| `dwell_cv` | ~0.9 | Trivial | **1–2%** |
| `post_space_flight` | ~0.9 | Easy | **1–2%** |
| `burst_rate` | ~0.7 | Easy | **~1%** |

**Combined realistic EER target (Tier 1 features + re-enable typing_speed):** ~14–18% EER
**Combined realistic EER target (all Tier 1 + Tier 2):** ~10–14% EER

> Note: EER reductions are not additive — features share partial signal, so diminishing returns apply. Estimates assume the Isolation Forest model is retrained with the new feature set.
