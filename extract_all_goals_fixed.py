import json
import os
import cv2
import subprocess
import glob
import argparse
from pathlib import Path

def extract_goal_clips(json_file, game_dir, output_dir, game_name):
    """
    Extract 15-second clips before goals from football match videos.
    
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
        goal_events = [event for event in annotations if event.get('label') == 'Goal']
    else:
        # Fallback if structure is different
        goal_events = [event for event in data if isinstance(event, dict) and event.get('label') == 'Goal']
    
    print(f"Game: {game_name} - Found {len(goal_events)} goal events")
    if len(goal_events) == 0:
        return
    
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
    
    # Process each goal event
    for i, goal in enumerate(goal_events):
        try:
            # Extract information from the goal event
            period = int(goal['gameTime'].split(' - ')[0])
            time_str = goal['gameTime'].split(' - ')[1]
            minutes, seconds = map(int, time_str.split(':'))
            team = goal.get('team', 'unknown')
            
            # Select correct video file based on period
            if period <= 0 or period > 2:
                print(f"Error: Invalid period {period} for goal at {goal['gameTime']}")
                continue
                
            video_path = video_files[period - 1]
            if video_path is None:
                print(f"Error: Video file for period {period} not available. Skipping goal at {goal['gameTime']}")
                continue
            
            # Extract the clip
            clip_name = f"{game_name}_goal_{i+1}_period{period}_{time_str.replace(':', 'm')}s_{team}.mkv"
            output_path = os.path.join(output_dir, clip_name)
            
            # Check if output file already exists - skip if it does
            if os.path.exists(output_path):
                print(f"Clip already exists: {output_path}. Skipping.")
                continue
            
            # Calculate the frames in the video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Could not open video file {video_path}")
                continue
                
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            
            # Convert goal time to seconds from the beginning of the half
            minutes_in_seconds = minutes * 60
            total_seconds = minutes_in_seconds + seconds
            goal_frame = int(total_seconds * fps)
            
            # Calculate start frame (15 seconds before goal)
            seconds_to_extract = 15
            start_frame = max(0, goal_frame - (seconds_to_extract * int(fps)))
            
            # Calculate time values for ffmpeg
            start_time = start_frame / fps
            duration = seconds_to_extract  # Exactly 15 seconds
            
            # Use ffmpeg to extract the clip
            # On the cluster, ffmpeg should be available in the system
            ffmpeg_cmd = "ffmpeg"
            
            # Try copy mode first (faster, no re-encoding)
            cmd = [
                ffmpeg_cmd,
                "-ss", f"{start_time:.3f}",  # Seek before input for more accuracy
                "-i", video_path,
                "-t", f"{duration:.3f}",
                "-c", "copy",       # Copy the codec (no re-encoding)
                "-y",               # Overwrite output files without asking
                output_path
            ]
            
            print(f"Extracting goal {i+1}: {goal['gameTime']} - {team} team")
            
            try:
                # On Linux (cluster), we don't need shell=True
                # Capture stderr for debugging
                result = subprocess.run(cmd, check=False, stderr=subprocess.PIPE)
                
                # Check if the command succeeded
                if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    print(f"Successfully saved clip to {output_path}")
                else:
                    # If the copy method fails, try again with re-encoding at a lower quality
                    print(f"Copy method failed. Trying with re-encoding...")
                    fallback_cmd = [
                        ffmpeg_cmd,
                        "-ss", f"{start_time:.3f}",  # Seek before input
                        "-i", video_path,
                        "-t", f"{duration:.3f}",
                        "-c:v", "mpeg4",      # Use mpeg4 codec (more widely compatible)
                        "-q:v", "5",          # Medium quality (lower = better)
                        "-c:a", "copy",       # Copy audio
                        "-y",                 # Overwrite output files
                        output_path
                    ]
                    
                    fallback_result = subprocess.run(fallback_cmd, check=False, stderr=subprocess.PIPE)
                    
                    if fallback_result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        print(f"Successfully saved clip using fallback method to {output_path}")
                    else:
                        print(f"Error extracting clip: {fallback_result.stderr.decode()}")
                        # Try one last method - just skip the problematic part
                        last_cmd = [
                            ffmpeg_cmd,
                            "-ss", f"{start_time:.3f}",  # Seek before input
                            "-i", video_path,
                            "-t", f"{duration:.3f}",
                            "-vcodec", "copy",       # Copy video
                            "-acodec", "copy",       # Copy audio
                            "-avoid_negative_ts", "make_zero",  # Handle negative timestamps
                            "-y",                 # Overwrite output files
                            output_path
                        ]
                        try:
                            last_result = subprocess.run(last_cmd, check=False)
                            if last_result.returncode == 0:
                                print(f"Final method succeeded: {output_path}")
                            else:
                                print(f"All extraction methods failed for this clip")
                        except Exception as e:
                            print(f"Exception in final attempt: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")
                return
                
        except (KeyError, ValueError, IndexError) as e:
            print(f"Error processing goal event: {e}")
            continue

def process_all_games(data_dir, output_dir, limit=None):
    """
    Process all games in the data directory and extract goal clips.
    
    Args:
        data_dir (str): Directory containing all game directories
        output_dir (str): Directory to save the extracted clips
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
            extract_goal_clips(json_file, game_dir, output_dir, game_name)
        else:
            print(f"Warning: No Labels-v2.json file found in {game_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract goal clips from multiple football games.')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Directory containing the game data')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Directory to save the extracted clips')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit the number of games to process')
    
    args = parser.parse_args()
    
    # Print configuration
    print(f"Data directory: {args.data_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Processing up to {args.limit} games")
    
    # Run the extraction
    process_all_games(args.data_dir, args.output_dir, args.limit)
