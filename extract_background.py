import json
import os
import cv2
import subprocess
import glob
import argparse
import random
from pathlib import Path

def extract_background_clips(json_file, game_dir, output_dir, game_name, clips_per_game=3):
    """
    Extract 15-second background clips (no goals) from football match videos.
    
    Args:
        json_file (str): Path to the JSON file with match annotations
        game_dir (str): Directory containing the match video files (MKV)
        output_dir (str): Directory to save the extracted clips
        game_name (str): Name of the game (used for naming output files)
        clips_per_game (int): Number of clips to extract per game
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
        goal_events = [event for event in annotations if event.get('label') == 'Goal']
    else:
        # Fallback if structure is different
        goal_events = [event for event in data if isinstance(event, dict) and event.get('label') == 'Goal']
    
    print(f"Game: {game_name} - Found {len(goal_events)} goal events to avoid")
    
    # Get video files from game directory
    # Look specifically for the 1_224p.mkv and 2_224p.mkv naming pattern
    first_half = os.path.join(game_dir, "1_224p.mkv")
    second_half = os.path.join(game_dir, "2_224p.mkv")
    
    video_files = [first_half, second_half]
    
    # Check if the files exist
    for i, file in enumerate(video_files):
        if not os.path.exists(file):
            print(f"Warning: Video file for half {i+1} not found: {file}")
            video_files[i] = None  # Mark as not available
    
    # Extract dangerous zones around goals
    danger_zones = []
    for goal in goal_events:
        try:
            # Extract information from the goal event
            period = int(goal['gameTime'].split(' - ')[0])
            time_str = goal['gameTime'].split(' - ')[1]
            minutes, seconds = map(int, time_str.split(':'))
            
            # Convert to seconds from start of half
            total_seconds = minutes * 60 + seconds
            
            # Add a buffer of 30 seconds before and after the goal
            danger_zones.append((period, max(0, total_seconds - 30), total_seconds + 30))
        except (KeyError, ValueError, IndexError) as e:
            print(f"Error processing goal event: {e}")
            continue
    
    # Keep track of extracted clips
    clips_extracted = 0
    attempts = 0
    max_attempts = 50  # Prevent infinite loops
    
    # Process each half to extract random background clips
    for period, video_path in enumerate(video_files, 1):
        if video_path is None:
            continue  # Skip if video file not available
        
        # Get video duration
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file {video_path}")
            continue
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        
        # Calculate duration in seconds
        duration_seconds = total_frames / fps if fps > 0 else 0
        
        # Attempt to extract clips until we have enough or reach max attempts
        while clips_extracted < clips_per_game and attempts < max_attempts:
            attempts += 1
            
            # Choose a random time, leaving margin at the start and end
            min_time = 20  # At least 20 seconds from start
            max_time = max(min_time, duration_seconds - 20)  # At least 20 seconds from end
            
            if max_time <= min_time:
                print(f"Video too short for period {period}")
                break
                
            random_time = random.uniform(min_time, max_time)
            random_minute = int(random_time // 60)
            random_second = int(random_time % 60)
            
            # Check if this time is in a danger zone
            is_in_danger_zone = False
            for danger_period, start_time, end_time in danger_zones:
                if period == danger_period:
                    clip_time = random_minute * 60 + random_second
                    if start_time <= clip_time <= end_time:
                        is_in_danger_zone = True
                        break
            
            if is_in_danger_zone:
                continue  # Skip this time, too close to a goal
            
            # Extract the clip
            clip_name = f"{game_name}_background_{clips_extracted+1}_period{period}_{random_minute}m{random_second}s.mkv"
            output_path = os.path.join(output_dir, clip_name)
            
            # Check if output file already exists - skip if it does
            if os.path.exists(output_path):
                print(f"Clip already exists: {output_path}. Skipping.")
                continue
            
            # Calculate time values for ffmpeg
            start_time = random_time
            duration = 15.0  # Exactly 15 seconds
            
            # Use ffmpeg to extract the clip
            ffmpeg_cmd = "ffmpeg"
            
            # First try with copy method (faster)
            cmd = [
                ffmpeg_cmd,
                "-ss", f"{start_time:.3f}",
                "-i", video_path,
                "-t", f"{duration:.3f}",
                "-c", "copy",       # Copy the codec (no re-encoding)
                "-y",               # Overwrite output files without asking
                output_path
            ]
            
            print(f"Extracting background clip {clips_extracted+1}: period {period} - {random_minute}:{random_second}")
            
            try:
                # On Linux (cluster), we don't need shell=True
                result = subprocess.run(cmd, check=False, stderr=subprocess.PIPE)
                
                # Check if the command succeeded
                if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    print(f"Successfully saved clip to {output_path}")
                    clips_extracted += 1
                else:
                    # If the copy method fails, try again with re-encoding
                    print(f"Copy method failed. Trying with re-encoding...")
                    fallback_cmd = [
                        ffmpeg_cmd,
                        "-ss", f"{start_time:.3f}",
                        "-i", video_path,
                        "-t", f"{duration:.3f}",
                        "-c:v", "mpeg4",      # Use mpeg4 codec (more compatible)
                        "-q:v", "5",          # Medium quality
                        "-c:a", "copy",       # Copy audio
                        "-y",                 # Overwrite output files
                        output_path
                    ]
                    
                    fallback_result = subprocess.run(fallback_cmd, check=False, stderr=subprocess.PIPE)
                    
                    if fallback_result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        print(f"Successfully saved clip using fallback method to {output_path}")
                        clips_extracted += 1
                    else:
                        print(f"Error extracting clip: {fallback_result.stderr.decode()}")
                        # Try one last method
                        last_cmd = [
                            ffmpeg_cmd,
                            "-ss", f"{start_time:.3f}",
                            "-i", video_path,
                            "-t", f"{duration:.3f}",
                            "-vcodec", "copy",
                            "-acodec", "copy",
                            "-avoid_negative_ts", "make_zero",
                            "-y",
                            output_path
                        ]
                        try:
                            last_result = subprocess.run(last_cmd, check=False)
                            if last_result.returncode == 0:
                                print(f"Final method succeeded: {output_path}")
                                clips_extracted += 1
                            else:
                                print(f"All extraction methods failed for this clip")
                        except Exception as e:
                            print(f"Exception in final attempt: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")
                
        # Check if we've extracted enough clips
        if clips_extracted >= clips_per_game:
            break

def process_all_games(data_dir, output_dir, clips_per_game=3, limit=None):
    """
    Process all games in the data directory and extract background clips.
    
    Args:
        data_dir (str): Directory containing all game directories
        output_dir (str): Directory to save the extracted clips
        clips_per_game (int): Number of background clips to extract per game
        limit (int, optional): Limit the number of games to process
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
    
    # Limit the number of games if specified
    if limit and isinstance(limit, int) and limit > 0:
        all_games = all_games[:limit]
        print(f"Limiting to {limit} games")
    
    # Process each game
    for i, game_dir in enumerate(all_games):
        print(f"\nProcessing game {i+1}/{len(all_games)}: {game_dir}")
        
        # Extract game name from directory path
        game_name = os.path.basename(game_dir)
        
        # Path to the JSON file with annotations
        json_file = os.path.join(game_dir, "Labels-v2.json")
        
        if os.path.exists(json_file):
            extract_background_clips(json_file, game_dir, output_dir, game_name, clips_per_game)
        else:
            print(f"Warning: No Labels-v2.json file found in {game_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract background clips (no goals) from multiple football games.')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Directory containing the game data')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Directory to save the extracted clips')
    parser.add_argument('--clips_per_game', type=int, default=3,
                        help='Number of background clips to extract per game')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit the number of games to process')
    
    args = parser.parse_args()
    
    # Set random seed for reproducibility
    random.seed(42)
    
    # Print configuration
    print(f"Data directory: {args.data_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Clips per game: {args.clips_per_game}")
    if args.limit:
        print(f"Processing up to {args.limit} games")
    else:
        print("Processing all games")
    
    # Run the extraction
    process_all_games(args.data_dir, args.output_dir, args.clips_per_game, args.limit)