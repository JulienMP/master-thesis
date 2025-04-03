import json
import os
import cv2
import subprocess
import glob
import argparse
from pathlib import Path



def extract_shot_clips(json_file, game_dir, output_dir, game_name):
    """
    Extract 15-second clips ending at the moment of shots on target
    that didn't result in goals immediately after.

    Args:
        json_file (str): Path to the JSON file with match annotations
        game_dir (str): Directory containing the match video files (MKV)
        output_dir (str): Directory to save the extracted clips
        game_name (str): Name of the game (used for naming output files)
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Load json data
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading JSON file {json_file}: {e}")
        return

    # The Labels-v2.json file has a specific structure with annotations as a list
    if 'annotations' in data:
        annotations = data['annotations']
    else:
        # Fallback if structure is different
        annotations = data if isinstance(data, list) else []

    # Sort all events by position to get chronological order might be useful, but not strictly necessary for this logic
    # sorted_events = sorted(annotations, key=lambda x: int(x.get('position', 0)))
    # Using original annotations list is fine here

    # Extract goal event times for checking proximity
    goal_event_times = []
    for event in annotations: # Iterate through original annotations
        if event.get('label') == 'Goal':
            try:
                period = int(event['gameTime'].split(' - ')[0])
                time_str = event['gameTime'].split(' - ')[1]
                minutes, seconds = map(int, time_str.split(':'))
                # Convert to total seconds from start of period
                total_seconds = minutes * 60 + seconds
                goal_event_times.append((period, total_seconds))
            except (KeyError, ValueError, IndexError):
                continue

    # Find shots on target that weren't immediately followed by a goal
    shot_events = []
    for event in annotations: # Iterate through original annotations again
        if event.get('label') == 'Shots on target':
            try:
                period = int(event['gameTime'].split(' - ')[0])
                time_str = event['gameTime'].split(' - ')[1]
                minutes, seconds = map(int, time_str.split(':'))
                team = event.get('team', 'unknown')
                position = int(event.get('position', 0)) # Keep position if needed for sorting later, maybe?

                # Check if this shot is close to a goal (e.g., within 2 seconds AFTER)
                # This filter ensures we don't pick shots that *immediately* result in a goal annotation.
                is_near_goal = False
                shot_time = minutes * 60 + seconds

                for goal_period, goal_time in goal_event_times:
                    if period == goal_period:
                        # Check if goal happens shortly AFTER the shot
                        time_diff = goal_time - shot_time
                        if 0 <= time_diff < 2:  # Goal within 2 seconds AFTER shot
                            is_near_goal = True
                            break

                # Only include shots that aren't immediately followed by goals
                if not is_near_goal:
                    shot_events.append({
                        'period': period,
                        'minutes': minutes,
                        'seconds': seconds,
                        'team': team,
                        'position': position, # Store position if needed
                        'gameTime': event['gameTime']
                    })
            except (KeyError, ValueError, IndexError) as e:
                print(f"Error processing shot event: {event}. Error: {e}")
                continue

    print(f"Game: {game_name} - Found {len(shot_events)} shots on target (excluding those immediately followed by goals)")
    if len(shot_events) == 0:
        return

    # Get video files (same as before)
    first_half = os.path.join(game_dir, "1_224p.mkv")
    second_half = os.path.join(game_dir, "2_224p.mkv")
    video_files = [first_half, second_half]
    for i, file in enumerate(video_files):
        if not os.path.exists(file):
            print(f"Warning: Video file for half {i+1} not found: {file}")
            video_files[i] = None

    # Process each valid shot event
    clips_extracted_count = 0 # clip_limit = 10 Example limit

    for i, shot in enumerate(shot_events):
        # Optional: Check clip limit
        # if clip_limit is not None and clips_extracted_count >= clip_limit:
        #    print(f"Reached clip limit of {clip_limit}. Stopping extraction for this game.")
        #    break

        try:
            period = shot['period']
            minutes = shot['minutes']
            seconds = shot['seconds']
            team = shot['team']

            # Select correct video file
            if period <= 0 or period > 2:
                print(f"Error: Invalid period {period} for shot at {shot['gameTime']}")
                continue
            video_path = video_files[period - 1]
            if video_path is None:
                print(f"Error: Video file for period {period} not available. Skipping shot at {shot['gameTime']}")
                continue

            # Format clip name
            time_str = f"{minutes:02d}:{seconds:02d}"
            clip_name = f"{game_name}_shot_{i+1}_period{period}_{time_str.replace(':', 'm')}s_{team}.mkv"
            output_path = os.path.join(output_dir, clip_name)

            if os.path.exists(output_path):
                print(f"Clip already exists: {output_path}. Skipping.")
                # clips_extracted_count += 1 # Increment if counting existing for limit
                continue

            # Get video FPS
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Could not open video file {video_path}")
                continue
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                 print(f"Warning: Could not determine FPS for {video_path}. Skipping shot.")
                 cap.release()
                 continue
            cap.release()

            # Convert shot time to seconds from the beginning of the half
            total_seconds = (minutes * 60) + seconds
            shot_frame = int(total_seconds * fps)

            # --- MODIFICATION START: Calculate 15 seconds BEFORE the shot ---
            seconds_to_extract = 15
            start_frame = max(0, shot_frame - (seconds_to_extract * int(fps)))
            duration = seconds_to_extract  # Duration is now just the seconds before
            start_time = start_frame / fps
            # --- MODIFICATION END ---

            # Use ffmpeg (consider putting -ss before -i for accuracy)
            ffmpeg_cmd = "ffmpeg"
            cmd = [
                ffmpeg_cmd,
                "-ss", f"{start_time:.3f}", # Seek before input
                "-i", video_path,
                "-t", f"{duration:.3f}",
                "-c", "copy",
                "-avoid_negative_ts", "make_zero", # Helps with copy mode
                "-y",
                output_path
            ]
            print(f"Extracting shot {i+1}: {shot['gameTime']} - {team} team (extracting {duration}s before)")

            try:
                result = subprocess.run(cmd, check=False, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    print(f"Successfully saved clip to {output_path}")
                    # clips_extracted_count += 1 # Increment if counting for limit
                else:
                    # Fallback with re-encoding (also use -ss before -i)
                    print(f"Copy method failed (Code: {result.returncode}). Error: {result.stderr}. Trying re-encoding...")
                    fallback_cmd = [
                        ffmpeg_cmd,
                        "-ss", f"{start_time:.3f}", # Seek before input
                        "-i", video_path,
                        "-t", f"{duration:.3f}",
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
                        # clips_extracted_count += 1 # Increment if counting for limit
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

        except (KeyError, ValueError, IndexError) as e:
            print(f"Error processing shot event {i+1}: {shot}. Error: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error processing shot event {i+1}: {shot}. Error: {e}")
            continue

def process_all_games(data_dir, output_dir):
    """
    Process all games in the data directory and extract shot clips.
    
    Args:
        data_dir (str): Directory containing all game directories
        output_dir (str): Directory to save the extracted clips
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all game directories
    all_games = []
    for root, dirs, files in os.walk(data_dir):
        # Look for directories that have the Labels-v2.json file and video files
        if "Labels-v2.json" in files and any(f.endswith("_224p.mkv") for f in files):
            all_games.append(root)
    
    print(f"Found {len(all_games)} potential game directories")
    print(f"Processing ALL games (no limit)")
    
    # Process each game
    for i, game_dir in enumerate(all_games):
        print(f"\nProcessing game {i+1}/{len(all_games)}: {game_dir}")
        
        # Extract game name from directory path
        game_name = os.path.basename(game_dir)
        
        # Path to the JSON file with annotations
        json_file = os.path.join(game_dir, "Labels-v2.json")
        
        if os.path.exists(json_file):
            extract_shot_clips(json_file, game_dir, output_dir, game_name)
        else:
            print(f"Warning: No Labels-v2.json file found in {game_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract clips of shots on target (without goals) from football games.')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Directory containing the game data')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Directory to save the extracted clips')
    
    args = parser.parse_args()
    
    # Print configuration
    print(f"Data directory: {args.data_dir}")
    print(f"Output directory: {args.output_dir}")
    print("Processing all available games")
    
    # Run the extraction
    process_all_games(args.data_dir, args.output_dir)