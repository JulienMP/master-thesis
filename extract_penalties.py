import json
import os
import cv2
import subprocess
import glob
import argparse
from pathlib import Path
import math

def get_event_time_seconds(event):
    """Helper function to get event time in total seconds for a period."""
    try:
        period = int(event['gameTime'].split(' - ')[0])
        time_str = event['gameTime'].split(' - ')[1]
        minutes, seconds = map(int, time_str.split(':'))
        total_seconds = (minutes * 60) + seconds
        return period, total_seconds
    except (KeyError, ValueError, IndexError, AttributeError):
        return None, None

def extract_penalty_clips(json_file, game_dir, output_dir, game_name, trigger_window=120):
    """
    Extracts 15-second clips starting 15s before the Foul/Card
    that immediately precedes a Penalty label.

    Args:
        json_file (str): Path to the JSON file with match annotations.
        game_dir (str): Directory containing the match video files (MKV).
        output_dir (str): Directory to save the extracted clips.
        game_name (str): Name of the game (used for naming output files).
        trigger_window (int): Max seconds before a Penalty to look for a trigger event. Defaults to 5.
    """
    os.makedirs(output_dir, exist_ok=True)

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading JSON file {json_file}: {e}")
        return

    annotations = data.get('annotations', [])
    if not annotations:
        print(f"No annotations found in {json_file}")
        return

    # Store events with their times for easier lookup
    events_with_time = []
    trigger_labels = {"Foul", "Yellow card", "Red card"}
    for event in annotations:
        period, total_seconds = get_event_time_seconds(event)
        label = event.get('label')
        if period is not None and label:
            events_with_time.append({
                'period': period,
                'time_seconds': total_seconds,
                'label': label,
                'team': event.get('team', 'unknown'),
                'gameTime': event.get('gameTime') # Keep original time string
            })

    # Sort events chronologically within each period
    events_with_time.sort(key=lambda x: (x['period'], x['time_seconds']))

    # Find Penalty events and look back for recent trigger events (Foul/Card)
    penalty_trigger_pairs = []
    for i, current_event in enumerate(events_with_time):
        if current_event['label'] == 'Penalty':
            penalty_period = current_event['period']
            penalty_time = current_event['time_seconds']

            # Look back within the specified window for a trigger event in the same period
            found_trigger = None
            for j in range(i - 1, -1, -1):
                prev_event = events_with_time[j]
                # Stop searching if we go too far back in time or into previous period
                if prev_event['period'] != penalty_period or (penalty_time - prev_event['time_seconds']) > trigger_window:
                    break

                if prev_event['label'] in trigger_labels:
                    found_trigger = prev_event
                    break # Found the most recent trigger event within the window

            if found_trigger:
                penalty_trigger_pairs.append({
                    'penalty_event': current_event,
                    'trigger_event': found_trigger
                })
                print(f"Found pair: Trigger '{found_trigger['label']}' at {found_trigger['gameTime']} -> Penalty at {current_event['gameTime']}")

    print(f"Game: {game_name} - Found {len(penalty_trigger_pairs)} potential Penalty sequences.")
    if len(penalty_trigger_pairs) == 0:
        return

    # --- Video File Handling ---
    first_half = os.path.join(game_dir, "1_224p.mkv")
    second_half = os.path.join(game_dir, "2_224p.mkv")
    video_files = [first_half, second_half]
    for i, file in enumerate(video_files):
        if not os.path.exists(file):
            print(f"Warning: Video file for half {i+1} not found: {file}")
            video_files[i] = None
    # --- End Video File Handling ---

    # Process each identified trigger->penalty pair
    clips_extracted_count = 0
    # clip_limit = 10 # Optional limit

    for idx, pair in enumerate(penalty_trigger_pairs):
        # Optional: Check clip limit
        # if clip_limit is not None and clips_extracted_count >= clip_limit:
        #    print(f"Reached clip limit of {clip_limit}. Stopping extraction for this game.")
        #    break

        penalty_event = pair['penalty_event']
        trigger_event = pair['trigger_event']
        period = trigger_event['period'] # Use trigger event's period
        trigger_time_sec = trigger_event['time_seconds']
        trigger_game_time_str = trigger_event['gameTime'].split(' - ')[1].replace(':', 'm')+'s' # For filename
        penalty_game_time_str = penalty_event['gameTime'].split(' - ')[1].replace(':', 'm')+'s' # For filename


        try:
            # Select correct video file
            if period <= 0 or period > 2:
                print(f"Error: Invalid period {period} for trigger event: {trigger_event['gameTime']}")
                continue
            video_path = video_files[period - 1]
            if video_path is None:
                print(f"Error: Video file for period {period} not found. Skipping sequence triggered at {trigger_event['gameTime']}")
                continue

            # --- Define Clip Name ---
            clip_name = f"{game_name}_penalty_clip_{idx+1}_period{period}_trigger{trigger_game_time_str}_penalty{penalty_game_time_str}.mkv"
            output_path = os.path.join(output_dir, clip_name)

            if os.path.exists(output_path):
                print(f"Clip already exists: {output_path}. Skipping.")
                # clips_extracted_count += 1 # Increment if counting existing for limit
                continue

            # --- Get Video FPS ---
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Could not open video file {video_path}")
                continue
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                 print(f"Warning: Could not determine FPS for {video_path}. Skipping sequence.")
                 cap.release()
                 continue
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_video_sec = total_frames / fps if fps > 0 else 0
            cap.release()
            # --- End Get Video FPS ---

            # --- Calculate Clip Boundaries ---
            # Start 15 seconds BEFORE the trigger event, duration is 15 seconds
            clip_duration_sec = 15
            clip_start_time_sec = max(0, trigger_time_sec - clip_duration_sec)
            # Ensure clip doesn't go beyond video duration
            clip_end_time_sec = min(duration_video_sec, clip_start_time_sec + clip_duration_sec)
            actual_duration = clip_end_time_sec - clip_start_time_sec

            if actual_duration < 1: # Avoid tiny clips if trigger is very early
                 print(f"Skipping sequence: Calculated duration too short ({actual_duration:.2f}s) for trigger at {trigger_event['gameTime']}")
                 continue
            # --- End Calculate Clip Boundaries ---


            # --- FFmpeg Extraction (using -ss before -i) ---
            ffmpeg_cmd = "ffmpeg"
            cmd = [
                ffmpeg_cmd,
                "-ss", f"{clip_start_time_sec:.3f}", # Start time
                "-i", video_path,
                "-t", f"{actual_duration:.3f}",     # Duration
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                output_path
            ]
            print(f"Extracting Penalty sequence {idx+1}: Trigger '{trigger_event['label']}' at {trigger_event['gameTime']}, Penalty at {penalty_event['gameTime']}")
            print(f"  -> Output: {output_path} (Start: {clip_start_time_sec:.2f}s, End: {clip_end_time_sec:.2f}s, Duration: {actual_duration:.2f}s)")

            try:
                result = subprocess.run(cmd, check=False, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    print(f"Successfully saved clip to {output_path}")
                    clips_extracted_count += 1
                else:
                    # Fallback with re-encoding
                    print(f"Copy method failed (Code: {result.returncode}). Error: {result.stderr}. Trying re-encoding...")
                    fallback_cmd = [
                        ffmpeg_cmd,
                        "-ss", f"{clip_start_time_sec:.3f}", # Start time
                        "-i", video_path,
                        "-t", f"{actual_duration:.3f}",     # Duration
                        "-c:v", "libx264",
                        "-preset", "fast",
                        "-crf", "23",
                        "-c:a", "aac",
                        "-b:a", "128k",
                        "-y",
                        output_path
                    ]
                    fallback_result = subprocess.run(fallback_cmd, check=False, stderr=subprocess.PIPE, text=True)
                    if fallback_result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        print(f"Successfully saved clip using re-encoding to {output_path}")
                        clips_extracted_count += 1
                    else:
                        print(f"Fallback extraction failed (Code: {fallback_result.returncode}). Error: {fallback_result.stderr}")
                        if os.path.exists(output_path):
                            try: os.remove(output_path)
                            except OSError as e: print(f"Error removing failed file: {e}")

            except Exception as e:
                print(f"Unexpected error during ffmpeg execution: {e}")
                if os.path.exists(output_path):
                     try: os.remove(output_path)
                     except OSError as oe: print(f"Error removing file after exception: {oe}")
            # --- End FFmpeg Extraction ---

        except Exception as e:
            print(f"Error processing trigger->penalty pair {idx+1} (Trigger at {trigger_event.get('gameTime', 'N/A')}): {e}")
            continue


def process_all_games(data_dir, output_dir, trigger_window=5):
    """
    Process all games in the data directory and extract penalty clips.

    Args:
        data_dir (str): Directory containing all game directories.
        output_dir (str): Directory to save the extracted clips.
        trigger_window (int): Max seconds before a Penalty to look for a trigger event.
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- Find Game Directories ---
    all_games = []
    pattern = os.path.join(data_dir, "*", "Labels-v2.json")
    json_files_found = glob.glob(pattern)
    if not json_files_found:
         print("Glob found no JSON files, trying os.walk...")
         for root, dirs, files in os.walk(data_dir):
             if "Labels-v2.json" in files:
                 json_files_found.append(os.path.join(root, "Labels-v2.json"))

    for json_path in json_files_found:
         game_dir_path = os.path.dirname(json_path)
         if glob.glob(os.path.join(game_dir_path, "*_224p.mkv")):
              all_games.append(game_dir_path)
    # --- End Find Game Directories ---

    print(f"Found {len(all_games)} potential game directories")

    # Process each game
    for i, game_dir in enumerate(all_games):
        print(f"\nProcessing game {i+1}/{len(all_games)}: {game_dir}")
        game_name = os.path.basename(game_dir)
        json_file = os.path.join(game_dir, "Labels-v2.json")

        if os.path.exists(json_file):
            extract_penalty_clips(json_file, game_dir, output_dir, game_name, trigger_window)
        else:
            print(f"Warning: No Labels-v2.json file found in {game_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract 15s clips ending at the Foul/Card that precedes a Penalty.')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Directory containing the game data')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Directory to save the extracted clips')
    parser.add_argument('--window', type=int, default=5,
                        help='Max seconds before a Penalty to look back for a trigger Foul/Card (default: 5)')

    args = parser.parse_args()

    print(f"Data directory: {args.data_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Penalty trigger lookback window: {args.window} seconds")
    print("Processing all available games")

    process_all_games(args.data_dir, args.output_dir, trigger_window=args.window)