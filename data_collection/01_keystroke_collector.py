import csv
import os
import time
from pynput import keyboard

LOG_FILE = "keystroke_log.csv"  # constant value

file_exists = os.path.isfile(LOG_FILE) # to check if file exists or not

csv_file = open(LOG_FILE, mode='a', newline="") # append mode so doesnt overwrite. newline because of windows compatibilty

writer = csv.writer(csv_file) # write object created to write everything in csv

if not file_exists:
    writer.writerow(["key_id","press_time","release_time"]) # if file is not there add these at the first row/headings

press_times = {} # dict to record press times 

def on_press(key):  # function for key press
    key_id = get_key_id(key)
    if key_id not in press_times: # to tackle key holding, only registers one key a instead of aaaaaaaaaaa
        press_times[key_id] = time.time() # record press time when key is pressed

def on_release(key): # function for key release
    key_id = get_key_id(key)
    release_time = time.time() # record release time

    press_time = press_times.pop(key_id,None) # pop the key that is released, from the dictionary

    if press_time is not None:
        writer.writerow([key_id,press_time,release_time]) # if press time is not None, add in csv

        csv_file.flush() # so that python doesnt hold a buffer instead directly saves the edits in the csv

        if key == keyboard.Key.esc:
            csv_file.close()
            return False # when ESC is pressed, key collector stops and closes the csv and returns false that signals the listener to stop too


def get_key_id(key): # function to get key ids
    try:
        return key.char # if we directly access special keys from here it will throw attribute error
    except AttributeError: # so whenever attribute error is there, convert that key into a string
        return str(key) 

print("Collecting keystrokes... Press ESC to stop.")

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join() # listener object created that will work in the background.

# why we pass on_press instead of on_press()?? because we dont want the output or the return value of the function
# instead we want to give the listener object the function that it can call itself when a key is pressed or released.
# listener.join is necessary as it makes the execution of the rest of the code stop, until the key collection is
# happening. when ESC is pressed it signals the listener that the process is over. and rest of the code can be written.
# if there is no listener.join() then the code wont really record any keystrokes and will end normally.

print(f"Done. Data saved to {LOG_FILE}")




