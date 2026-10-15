"""
src/05_real_time_monitor.py
Real-Time Continuous Authentication Background Monitor
------------------------------------------------------
Monitors live keyboard events via pynput, continuously extracts 9 kinematic features
across sliding windows (W=50, S=10), scores anomaly levels via Isolation Forest,
and executes dynamic consensus ramp-up (3/3 -> 4/5 -> 8/10) with 30s idle-timeout reset.
"""

import os  # for path manipulation, checking files, and directory navigation
import sys  # system-specific parameters, terminal arguments, and exit handling
import time  # timestamp recording for key press, release, and flight calculation
import argparse  # for parsing command line options like --lock and --idle-timeout
import ctypes  # allows calling native Windows C libraries (user32.dll for locking PC)
from collections import deque  # double-ended queue for fast O(1) FIFO consensus buffer
import joblib  # to load saved machine learning models (.pkl) from Phase 3
import pandas as pd  # for DataFrame manipulation and named feature column alignment
import numpy as np  # mathematical operations, array slicing, and NaN handling
from pynput import keyboard  # low-level OS keyboard event hook (WH_KEYBOARD_LL on Windows)

try:
    import winsound  # native Windows module for playing alert sounds and beeps
    HAS_WINSOUND = True  # flag indicating Windows sound is available
except ImportError:
    HAS_WINSOUND = False  # fallback if running on non-Windows or headless system

# Default Hyperparameters (calibrated in Phase 2, 3, and 4)
DEFAULT_THRESHOLD = -0.0518  # EER cutoff from Phase 3: scores above this are anomalous
DEFAULT_BUFFER_SIZE = 10  # maximum number of consecutive window decisions held in voting queue
DEFAULT_FULL_VOTE_THRESHOLD = 8  # required anomalous flags once buffer is fully saturated (8 of 10)
DEFAULT_WINDOW_SIZE = 50  # number of physical keystrokes required to compute distribution statistics
DEFAULT_SLIDE_STEP = 10  # window advances forward by 10 keystrokes between evaluation steps
DEFAULT_MAX_VALID_TIME = 2.0  # filter out flight/dwell times >= 2.0s so pauses don't distort statistics
DEFAULT_IDLE_TIMEOUT_SEC = 30.0  # inactivity gap that resets buffers to stop desk takeover corruption

# The exact 9 kinematic features matching Phase 2 extraction and Phase 3 model training
FEATURE_COLS = [
    "avg_dwell",  # mean duration finger holds key down (release - press)
    "std_dwell",  # standard deviation of dwell times across the 50-keystroke window
    "avg_flight",  # mean time elapsed between lifting key A and striking key B
    "std_flight",  # standard deviation of flight times across the window
    "typing_speed",  # keystroke cadence measured in keys per second
    "backspace_rate",  # proportion of keystrokes that are backspaces (error correction)
    "avg_space_dwells",  # mean dwell time specifically on spacebars (thumb motor rhythm)
    "overlap_rate",  # fraction of flight times < 0 (pressing next key before releasing current)
    "long_pause_rate",  # fraction of flight times > 0.5s (hesitation and thinking pauses)
]


class DynamicRampUpBuffer:
    """
    Fixed-capacity FIFO consensus buffer with a dynamic ramp-up schedule.
    - len < 3: Insufficient samples to draw statistical confidence (wait)
    - len == 3: 3 of 3 (100% consensus, triggers after ~70 keystrokes)
    - len in (4, 5): >= 4 anomalous flags required
    - len in (6, 7): >= 6 anomalous flags required
    - len in (8, 9): >= 7 anomalous flags required
    - len == 10: >= 8 of 10 anomalous flags (saturated baseline)
    """
    def __init__(self, maxlen=DEFAULT_BUFFER_SIZE, full_vote_threshold=DEFAULT_FULL_VOTE_THRESHOLD, use_ramp_up=True):
        self.maxlen = maxlen  # maximum capacity of queue (10 items)
        self.full_vote_threshold = full_vote_threshold  # saturated threshold (8 items)
        self.use_ramp_up = use_ramp_up  # toggle for dynamic ramp-up vs static fixed voting
        self.buffer = deque(maxlen=maxlen)  # deque automatically discards oldest left item when full

    def append(self, is_anomalous: bool) -> bool:
        self.buffer.append(bool(is_anomalous))  # add newest window verdict to the right of queue
        return self.is_alert_triggered()  # immediately evaluate if alert threshold is satisfied

    def is_alert_triggered(self) -> bool:
        curr_len = len(self.buffer)  # number of window verdicts currently stored
        count = sum(self.buffer)  # count how many entries are True (anomalous)

        if not self.use_ramp_up:
            return count >= self.full_vote_threshold  # legacy mode: require 8 flags unconditionally

        if curr_len < 3:
            return False  # insufficient history: 1 or 2 windows cannot trigger an alert
        elif curr_len == 3:
            return count == 3  # window 3 (~70 keys): require 100% consensus (3 out of 3)
        elif curr_len <= 5:
            return count >= 4  # windows 4-5 (~80-90 keys): require at least 4 flags
        elif curr_len <= 7:
            return count >= 6  # windows 6-7 (~100-110 keys): require at least 6 flags
        elif curr_len <= 9:
            return count >= 7  # windows 8-9 (~120-130 keys): require at least 7 flags
        else:
            return count >= self.full_vote_threshold  # window 10+ (saturated): standard 8 of 10

    def clear(self):
        self.buffer.clear()  # flushes the queue back to length 0 (used by idle watchdog)

    def __len__(self):
        return len(self.buffer)  # allows calling len(buffer) directly on the object

    def __iter__(self):
        return iter(self.buffer)  # allows iterating over buffer elements (e.g. sum(buffer))


class ContinuousAuthDecisionEngine:
    """
    Stateful streaming decision engine.
    Ingests live hardware events, handles idle watchdog resets, maintains
    bounded O(1) memory, and computes window features & anomaly verdicts.
    """
    def __init__(
        self,
        model,  # loaded pre-trained Isolation Forest model from Phase 3
        scaler,  # loaded fitted StandardScaler from Phase 3
        threshold: float = DEFAULT_THRESHOLD,  # decision threshold (-0.0518)
        window_size: int = DEFAULT_WINDOW_SIZE,  # window size (50 keystrokes)
        slide_step: int = DEFAULT_SLIDE_STEP,  # stride step (10 keystrokes)
        max_valid_time: float = DEFAULT_MAX_VALID_TIME,  # outlier suppression cutoff (2.0s)
        idle_timeout_sec: float = DEFAULT_IDLE_TIMEOUT_SEC,  # watchdog threshold (30.0s)
        idle_reset_enabled: bool = True,  # whether watchdog resets state on pauses
        use_ramp_up: bool = True,  # whether dynamic ramp-up schedule is enabled
        full_vote_threshold: int = DEFAULT_FULL_VOTE_THRESHOLD,  # mature threshold (8 of 10)
        buffer_size: int = DEFAULT_BUFFER_SIZE  # buffer capacity (10 windows)
    ):
        self.model = model  # store model reference
        self.scaler = scaler  # store scaler reference
        self.threshold = threshold  # anomaly boundary
        self.window_size = window_size  # sample size per window
        self.slide_step = slide_step  # evaluation stride
        self.max_valid_time = max_valid_time  # outlier clamp
        self.idle_timeout_sec = idle_timeout_sec  # idle timer limit
        self.idle_reset_enabled = idle_reset_enabled  # watchdog active flag

        # Initialize the downstream consensus decision buffer
        self.buffer = DynamicRampUpBuffer(
            maxlen=buffer_size,
            full_vote_threshold=full_vote_threshold,
            use_ramp_up=use_ramp_up
        )

        self.raw_events_buffer = []  # upstream queue of raw key event dicts
        self.last_release_time = None  # timestamp of the most recently released key
        self.keystrokes_since_last_evaluation = 0  # counter tracking keys typed since last window
        self.total_keystrokes = 0  # lifetime keystrokes processed in this session
        self.total_evaluations = 0  # lifetime window evaluations performed
        self.total_alerts = 0  # lifetime alert windows triggered
        self.watchdog_resets = 0  # counter tracking how many times watchdog flushed state

    def reset(self):
        """Flushes upstream sliding window and downstream decision queue."""
        self.raw_events_buffer.clear()  # wipe raw keystroke window so imposter keys don't blend with genuine
        self.buffer.clear()  # wipe consensus queue so imposter encounters fresh 3/3 ramp-up schedule
        self.keystrokes_since_last_evaluation = 0  # reset stride counter
        self.last_release_time = None  # reset release time reference
        self.watchdog_resets += 1  # increment reset counter for reporting

    def _extract_features(self, window_slice) -> dict:
        """Extracts 9 kinematic features from a 50-keystroke window."""
        window_df = pd.DataFrame(window_slice)  # convert list of event dicts to DataFrame
        duration = window_df["release_time"].iloc[-1] - window_df["press_time"].iloc[0]  # total time taken
        n_keys = len(window_df)  # count total keys in this window (always 50)
        
        # Flight calculation: drop terminal NaN and remove pauses >= 2.0s
        valid_flights = window_df["flight"].dropna()  # drop unresolved flight from newest key
        valid_flights = valid_flights[(valid_flights >= 0) & (valid_flights < self.max_valid_time)]  # filter
        
        backspace_count = (window_df["key_id"] == "Key.backspace").sum()  # count backspace strikes
        space_mask = window_df["key_id"] == "Key.space"  # boolean mask for spacebar strikes
        space_dwells = window_df.loc[space_mask, "dwell"]  # extract dwell times for spacebars
        
        all_flights = window_df["flight"].dropna()  # all flights including negative (overlaps)
        overlap_rate = float((all_flights < 0).mean()) if len(all_flights) > 0 else 0.0  # chord overlap rate
        long_pause_rate = float((valid_flights > 0.5).mean()) if len(valid_flights) > 0 else 0.0  # pauses > 500ms

        # Return structured dictionary matching FEATURE_COLS
        return {
            "avg_dwell": float(window_df["dwell"].mean()),  # mean dwell time
            "std_dwell": float(window_df["dwell"].std()),  # dwell variance
            "avg_flight": float(valid_flights.mean()) if len(valid_flights) > 0 else 0.0,  # mean flight
            "std_flight": float(valid_flights.std()) if len(valid_flights) > 0 else 0.0,  # flight variance
            "typing_speed": float(n_keys / duration) if duration > 0 else 0.0,  # speed in keys per second
            "backspace_rate": float(backspace_count / n_keys),  # backspace proportion
            "avg_space_dwells": float(space_dwells.mean()) if len(space_dwells) > 0 else 0.0,  # space dwell
            "overlap_rate": overlap_rate,  # fraction of key chords pressed before release
            "long_pause_rate": long_pause_rate,  # fraction of pauses exceeding 0.5s
        }

    def add_keystroke(self, key_id: str, press_time: float, release_time: float):
        """
        Ingests a single raw hardware event (key_id, press_time, release_time).
        Returns a dict of evaluation metrics if an evaluation was triggered, else None.
        """
        dwell = release_time - press_time  # calculate physical key dwell time
        if dwell <= 0 or dwell >= self.max_valid_time:
            return None  # discard corrupted event or key held down for > 2 seconds

        # Watchdog check: compare current press time with previous release time
        was_reset = False  # flag to track if this key triggered a reset
        if self.last_release_time is not None:
            idle_gap = press_time - self.last_release_time  # gap between keys
            if self.idle_reset_enabled and idle_gap >= self.idle_timeout_sec:
                self.reset()  # user was idle for >= 30s: flush stale buffers
                was_reset = True  # mark that watchdog fired

        # Retroactive flight calculation: resolve transition from key k-1 to key k
        if len(self.raw_events_buffer) > 0 and not was_reset:
            self.raw_events_buffer[-1]["flight"] = press_time - self.last_release_time  # bind delta

        # Package current event into a dictionary
        event = {
            "key_id": key_id,  # character or token name
            "press_time": press_time,  # timestamp of key-down
            "release_time": release_time,  # timestamp of key-up
            "dwell": dwell,  # physical contact duration
            "flight": np.nan  # flight to NEXT key is unknown until next key arrives
        }
        self.raw_events_buffer.append(event)  # add event to raw queue
        self.last_release_time = release_time  # update last release timestamp
        self.total_keystrokes += 1  # increment session key counter
        self.keystrokes_since_last_evaluation += 1  # increment stride counter

        # Memory ceiling: maintain strict O(1) space complexity by trimming buffer
        if len(self.raw_events_buffer) > self.window_size * 2:
            self.raw_events_buffer = self.raw_events_buffer[-self.window_size:]  # keep only recent 50 keys

        # Check if sliding window is ready for machine learning evaluation
        if len(self.raw_events_buffer) >= self.window_size:
            # Trigger evaluation if it's the very first window or if 10 new keystrokes have passed
            if self.total_evaluations == 0 or self.keystrokes_since_last_evaluation >= self.slide_step:
                window_slice = self.raw_events_buffer[-self.window_size:]  # take the last 50 keys
                features = self._extract_features(window_slice)  # compute 9 kinematic features
                
                # Wrap in named DataFrame to preserve feature column alignment for StandardScaler
                feat_df = pd.DataFrame([[features[c] for c in FEATURE_COLS]], columns=FEATURE_COLS)
                
                scaled = self.scaler.transform(feat_df)  # normalize features with fitted scaler
                score = float(-self.model.decision_function(scaled)[0])  # negate decision function
                is_anom = score > self.threshold  # score above -0.0518 is anomalous
                alert = self.buffer.append(is_anom)  # append boolean verdict to consensus buffer

                self.total_evaluations += 1  # increment evaluation counter
                self.keystrokes_since_last_evaluation = 0  # reset stride counter back to 0
                if alert:
                    self.total_alerts += 1  # increment alert counter if alert fired

                # Return structured dictionary of results
                return {
                    "evaluated": True,  # confirmation that an evaluation occurred
                    "keystroke_idx": self.total_keystrokes,  # current key number
                    "score": score,  # continuous anomaly score
                    "is_anomalous": is_anom,  # per-window anomaly verdict
                    "alert": alert,  # multi-window consensus alert state (True/False)
                    "buffer_depth": len(self.buffer),  # active queue length
                    "consensus_count": sum(self.buffer),  # number of anomalous flags in queue
                    "total_evaluations": self.total_evaluations,  # total evaluations to date
                    "total_alerts": self.total_alerts,  # total alerts to date
                    "features": features,  # raw extracted feature values
                    "watchdog_reset": was_reset  # whether watchdog reset on this window
                }
        return None  # return None when keystrokes are buffering between strides


def get_key_id(key) -> str:
    """Safe key normalization matching Phase 1."""
    try:
        return key.char if key.char is not None else str(key)  # normal alphanumeric character
    except AttributeError:
        return str(key)  # special key like Key.space or Key.backspace converted to string


def trigger_alert_actions(result: dict, lock_workstation: bool):
    """Executes defensive actions upon confirmed intruder alert."""
    if HAS_WINSOUND:
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)  # emit Windows warning sound
        except Exception:
            pass  # silent fallback if audio driver is busy or muted

    # Display high-visibility warning banner in terminal
    print("\n" + "=" * 65)
    print("🚨 [SECURITY ALERT] SUSTAINED ANOMALOUS TYPING RHYTHM DETECTED!")
    print(f"   Consensus: {result['consensus_count']}/{result['buffer_depth']} flags anomalous")
    print(f"   Score: {result['score']:.4f} (Threshold: {DEFAULT_THRESHOLD:.4f})")
    print(f"   Typing Speed: {result['features']['typing_speed']:.2f} keys/s | Dwell: {result['features']['avg_dwell']:.3f}s")
    
    if lock_workstation:
        print("🔒 [ACTION] High-Security Lock enabled: Locking Windows Workstation now!")
        print("=" * 65 + "\n")
        try:
            ctypes.windll.user32.LockWorkStation()  # call Windows API to physically lock desktop
        except Exception as e:
            print(f"Failed to lock workstation: {e}")  # print error if ctypes call fails
    else:
        print("⚠️ [ACTION] Workstation lock is disabled (Run with --lock to enable auto-lock).")
        print("=" * 65 + "\n")


def resolve_paths(model_arg, scaler_arg):
    """Finds model and scaler files across relative directories."""
    # List of candidate directories to search
    search_dirs = [
        os.getcwd(),  # current working directory
        os.path.dirname(os.path.abspath(__file__)),  # directory containing this script (src/)
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),  # project root directory
    ]
    
    model_path = None  # placeholder for found model path
    scaler_path = None  # placeholder for found scaler path

    # Search through candidate directories
    for d in search_dirs:
        m_cand = os.path.join(d, model_arg)  # candidate model path
        if os.path.isfile(m_cand) and model_path is None:
            model_path = m_cand  # assign if file physically exists

        s_cand = os.path.join(d, scaler_arg)  # candidate scaler path
        if os.path.isfile(s_cand) and scaler_path is None:
            scaler_path = s_cand  # assign if file physically exists

    # Ensure both files were found or raise explicit error
    if not model_path or not os.path.isfile(model_path):
        raise FileNotFoundError(f"Trained model not found (searched: {model_arg})")
    if not scaler_path or not os.path.isfile(scaler_path):
        raise FileNotFoundError(f"Fitted scaler not found (searched: {scaler_arg})")

    return model_path, scaler_path  # return verified absolute file paths


def main():
    # Setup command-line argument parser
    parser = argparse.ArgumentParser(
        description="Keystroke Dynamics Continuous Authentication Live Monitor"
    )
    # Define CLI options and their defaults
    parser.add_argument("--model", default="isolation_forest_model.pkl", help="Path to trained model (.pkl)")
    parser.add_argument("--scaler", default="scaler.pkl", help="Path to fitted StandardScaler (.pkl)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Anomaly score threshold (EER = -0.0518)")
    parser.add_argument("--idle-timeout", type=float, default=DEFAULT_IDLE_TIMEOUT_SEC, help="Watchdog inactivity timeout in seconds")
    parser.add_argument("--lock", action="store_true", help="Physically lock Windows workstation upon sustained alert")
    parser.add_argument("--no-ramp-up", action="store_true", help="Use fixed 8-of-10 buffer instead of dynamic ramp-up")
    args = parser.parse_args()  # parse arguments passed via terminal

    # Locate and load model and scaler
    model_path, scaler_path = resolve_paths(args.model, args.scaler)  # resolve full paths
    model = joblib.load(model_path)  # deserialize trained Isolation Forest model
    scaler = joblib.load(scaler_path)  # deserialize fitted StandardScaler

    # Instantiate the decision engine
    engine = ContinuousAuthDecisionEngine(
        model=model,  # pass model
        scaler=scaler,  # pass scaler
        threshold=args.threshold,  # pass threshold cutoff
        idle_timeout_sec=args.idle_timeout,  # pass watchdog timeout
        use_ramp_up=(not args.no_ramp_up)  # pass ramp-up preference
    )

    press_times = {}  # dictionary to record key-down timestamps and prevent holding auto-repeat
    is_running = True  # flag to gracefully control listener loop

    # Print startup banner and configuration HUD
    print("\n" + "=" * 65)
    print("   KEYSTROKE DYNAMICS CONTINUOUS AUTHENTICATION MONITOR")
    print("=" * 65)
    print(f"• Model:           {os.path.basename(model_path)}")  # show loaded model file name
    print(f"• Anomaly Cutoff:  {args.threshold:.4f} (EER calibrated)")  # show score cutoff
    print(f"• Strategy:        {'Dynamic Ramp-Up (3/3 -> 8/10)' if not args.no_ramp_up else 'Fixed 8-of-10'}")  # show voting strategy
    print(f"• Idle Watchdog:   {args.idle_timeout:.1f} seconds")  # show watchdog timer
    print(f"• Lock On Alert:   {'ENABLED (Will lock workstation)' if args.lock else 'DISABLED (Safe monitoring mode)'}")  # show lock mode
    print("=" * 65)
    print("Type naturally in any application. Press [ESC] in this window to stop.\n")

    # Callback function triggered every time a key is physically pressed down
    def on_press(key):
        nonlocal is_running  # access outer running flag
        if not is_running:
            return False  # exit immediately if user stopped the script
        key_id = get_key_id(key)  # convert key object to string identifier
        # Typematic repeat filter: only record timestamp if key isn't already held down
        if key_id not in press_times:
            press_times[key_id] = time.time()  # record physical down-stroke time

    # Callback function triggered every time a key is physically released
    def on_release(key):
        nonlocal is_running  # access outer running flag
        if not is_running:
            return False  # exit immediately if user stopped the script
            
        release_time = time.time()  # capture physical up-stroke timestamp
        key_id = get_key_id(key)  # convert key object to string identifier
        press_time = press_times.pop(key_id, None)  # atomically pop corresponding press time from dictionary

        # If press_time exists, we have a complete hardware event (press -> release)
        if press_time is not None:
            res = engine.add_keystroke(key_id, press_time, release_time)  # feed hardware event into decision engine
            # If an evaluation was performed (every 10 keys after 50 keys), print HUD line
            if res:
                status = "🚨 ALERT " if res["alert"] else "✅ OK    "  # alert status icon
                flag_str = "ANOMALY" if res["is_anomalous"] else "NORMAL "  # window verdict
                print(
                    f"[{status}] Window #{res['total_evaluations']:<3} | "
                    f"Keys: {res['keystroke_idx']:<4} | "
                    f"Score: {res['score']:+.4f} ({flag_str}) | "
                    f"Consensus: {res['consensus_count']}/{res['buffer_depth']} | "
                    f"Speed: {res['features']['typing_speed']:4.1f} k/s | "
                    f"Dwell: {res['features']['avg_dwell']*1000:4.0f}ms"
                )

                # If consensus alert triggered, execute defensive actions (audio/lock)
                if res["alert"]:
                    trigger_alert_actions(res, args.lock)  # call alert handler

        # Check for escape key to terminate session gracefully
        if key == keyboard.Key.esc:
            print("\n[ESC pressed] Terminating live listener...")  # notify user
            is_running = False  # set flag to False
            return False  # returning False tells pynput Listener to stop its background thread

    # Setup and launch the background low-level keyboard listener
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()  # blocks main script thread until on_release returns False (ESC pressed)
        except KeyboardInterrupt:
            print("\n[Ctrl+C] Interrupted by user.")  # handle terminal interrupt cleanly

    # Display session summary report upon termination
    print("\n" + "=" * 65)
    print("SESSION SUMMARY REPORT")
    print("=" * 65)
    print(f"• Total Keystrokes Logged:     {engine.total_keystrokes}")  # total keys typed
    print(f"• Window Evaluations:          {engine.total_evaluations}")  # total windows scored
    print(f"• Alert Windows Triggered:     {engine.total_alerts}")  # total windows in alert state
    print(f"• Watchdog Idle Resets:        {engine.watchdog_resets}")  # total times watchdog cleared state
    print(f"• False Alert Rate:            {engine.total_alerts / max(engine.total_evaluations, 1) * 100:.2f}%")  # alert percentage
    print("=" * 65 + "\n")


# Entrypoint guard: executes main() only when script is run directly from command line
if __name__ == "__main__":
    main()

# Why pass on_press and on_release as callbacks instead of calling them with on_press()?
# Because we do not want to execute the functions immediately when setting up the script.
# Instead, we pass the function references to pynput.keyboard.Listener so that the Windows OS
# message pump can invoke them automatically whenever a hardware keyboard interrupt occurs.
# listener.join() is necessary because keyboard.Listener runs on a separate worker thread.
# Calling listener.join() blocks the main thread from terminating, keeping the daemon alive
# until the ESC key returns False to close the listener.

# Why pass on_press and on_release as callbacks instead of calling them with on_press()?
# Because we do not want to execute the functions immediately when setting up the script.
# Instead, we pass the function references to pynput.keyboard.Listener so that the Windows OS
# message pump can invoke them automatically whenever a hardware keyboard interrupt occurs.
# listener.join() is necessary because keyboard.Listener runs on a separate worker thread.
# Calling listener.join() blocks the main thread from terminating, keeping the daemon alive
# until the ESC key returns False to close the listener.

