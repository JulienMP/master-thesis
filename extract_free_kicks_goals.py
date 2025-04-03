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

def extract_freekick_goal_clips(json_file, game_dir, output_dir, game_name, freekick_window=10):
    """
    Extract 15-second clips ending just before a goal that resulted from a recent free kick.

    Args:
        json_file (str): Path to the JSON file with match annotations.
        game_dir (str): Directory containing the match video files (MKV).
        output_dir (str): Directory to save the extracted clips.
        game_name (str): Name of the game (used for naming output files).
        freekick_window (int): Max seconds before a goal to look for a free kick. Defaults to 10.
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
    for event in annotations:
        period, total_seconds = get_event_time_seconds(event)
        label = event.get('label')
        if period is not None and label:
            events_with_time.append({
                'period': period,
                'time_seconds': total_seconds,
                'label': label,
                'team': event.get('team', 'unknown'),
                'gameTime': event.get('gameTime') # Keep original time string for naming
            })

    # Sort events chronologically within each period
    events_with_time.sort(key=lambda x: (x['period'], x['time_seconds']))

    # Find Goal events and look back for recent Free Kicks
    freekick_goal_pairs = []
    for i, current_event in enumerate(events_with_time):
        if current_event['label'] == 'Goal':
            goal_period = current_event['period']
            goal_time = current_event['time_seconds']
            goal_game_time = current_event['gameTime']
            goal_team = current_event['team']

            # Look back within the specified window for a free kick in the same period
            found_freekick = None
            for j in range(i - 1, -1, -1):
                prev_event = events_with_time[j]
                # Stop searching if we go too far back in time or into previous period
                if prev_event['period'] != goal_period or (goal_time - prev_event['time_seconds']) > freekick_window:
                    break

                if prev_event['label'] in ["Direct free-kick", "Indirect free-kick"]:
                    # Check if the freekick team is the same as the goal scoring team (usually is, but good check)
                    # Or allow if teams are different (e.g. own goal from free kick?) - currently allowing any team FK.
                    found_freekick = prev_event
                    break # Found the most recent free kick within the window

            if found_freekick:
                freekick_goal_pairs.append({
                    'goal_event': current_event,
                    'freekick_event': found_freekick
                })
                print(f"Found pair: Free kick at {found_freekick['gameTime']} -> Goal at {goal_game_time}")

    print(f"Game: {game_name} - Found {len(freekick_goal_pairs)} potential free kick -> goal sequences.")
    if len(freekick_goal_pairs) == 0:
        return

    # --- Video File Handling (same as previous scripts) ---
    first_half = os.path.join(game_dir, "1_224p.mkv")
    second_half = os.path.join(game_dir, "2_224p.mkv")
    video_files = [first_half, second_half]
    for i, file in enumerate(video_files):
        if not os.path.exists(file):
            print(f"Warning: Video file for half {i+1} not found: {file}")
            video_files[i] = None
    # --- End Video File Handling ---

    # Process each identified freekick->goal pair
    clips_extracted_count = 0
    # clip_limit = 10 # Optional limit

    for idx, pair in enumerate(freekick_goal_pairs):
        # Optional: Check clip limit
        # if clip_limit is not None and clips_extracted_count >= clip_limit:
        #    print(f"Reached clip limit of {clip_limit}. Stopping extraction for this game.")
        #    break

        goal_event = pair['goal_event']
        freekick_event = pair['freekick_event']
        period = goal_event['period']
        goal_time_sec = goal_event['time_seconds']
        goal_game_time_str = goal_event['gameTime'].split(' - ')[1].replace(':', 'm')+'s' # For filename
        fk_game_time_str = freekick_event['gameTime'].split(' - ')[1].replace(':', 'm')+'s' # For filename

        try:
            # Select correct video file
            if period <= 0 or period > 2:
                print(f"Error: Invalid period {period} for goal event: {goal_event['gameTime']}")
                continue
            video_path = video_files[period - 1]
            if video_path is None:
                print(f"Error: Video file for period {period} not found. Skipping sequence ending at {goal_event['gameTime']}")
                continue

            # --- Define Clip Name ---
            clip_name = f"{game_name}_freekick_goal_{idx+1}_period{period}_fk{fk_game_time_str}_goal{goal_game_time_str}.mkv"
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
            cap.release()
            # --- End Get Video FPS ---

            # --- Calculate Clip Boundaries ---
            # Extract 15 seconds ending just BEFORE the goal time
            clip_duration_sec = 15
            # Use math.nextafter to step back slightly from goal time to avoid including the exact frame
            clip_end_time_sec = math.nextafter(goal_time_sec, goal_time_sec - 1)
            clip_start_time_sec = max(0, clip_end_time_sec - clip_duration_sec)
            # Adjust duration if start time was clamped to 0
            actual_duration = clip_end_time_sec - clip_start_time_sec

            if actual_duration < 1: # Avoid tiny clips if goal is very early
                 print(f"Skipping sequence: Calculated duration too short ({actual_duration:.2f}s) for goal at {goal_event['gameTime']}")
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
            print(f"Extracting free kick->goal sequence {idx+1}: FK at {freekick_event['gameTime']}, Goal at {goal_event['gameTime']}")
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
            print(f"Error processing freekick->goal pair {idx+1} (Goal at {goal_event.get('gameTime', 'N/A')}): {e}")
            continue


def process_all_games(data_dir, output_dir, freekick_window=10):
    """
    Process all games in the data directory and extract free kick->goal clips.

    Args:
        data_dir (str): Directory containing all game directories.
        output_dir (str): Directory to save the extracted clips.
        freekick_window (int): Max seconds before a goal to look for a free kick.
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- Find Game Directories (same as previous scripts) ---
    all_games = []
    pattern = os.path.join(data_dir, "*", "Labels-v2.json")
    for json_path in glob.glob(pattern):
         game_dir_path = os.path.dirname(json_path)
         if glob.glob(os.path.join(game_dir_path, "*_224p.mkv")):
              all_games.append(game_dir_path)
    if not all_games:
         print("Glob didn't find games, falling back to os.walk...")
         for root, dirs, files in os.walk(data_dir):
             if "Labels-v2.json" in files and any(f.endswith("_224p.mkv") for f in files):
                 all_games.append(root)
    # --- End Find Game Directories ---

    print(f"Found {len(all_games)} potential game directories")

    # Process each game
    for i, game_dir in enumerate(all_games):
        print(f"\nProcessing game {i+1}/{len(all_games)}: {game_dir}")
        game_name = os.path.basename(game_dir)
        json_file = os.path.join(game_dir, "Labels-v2.json")

        if os.path.exists(json_file):
            extract_freekick_goal_clips(json_file, game_dir, output_dir, game_name, freekick_window)
        else:
            print(f"Warning: No Labels-v2.json file found in {game_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract 15s clips ending just before goals that resulted from recent free kicks.')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Directory containing the game data')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Directory to save the extracted clips')
    parser.add_argument('--window', type=int, default=10,
                        help='Max seconds before a goal to look back for a free kick (default: 10)')

    args = parser.parse_args()

    print(f"Data directory: {args.data_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Free kick lookback window: {args.window} seconds")
    print("Processing all available games")

    process_all_games(args.data_dir, args.output_dir, freekick_window=args.window)