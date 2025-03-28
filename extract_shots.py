import json
import os
import cv2
import subprocess
import glob
import argparse
from pathlib import Path

def extract_shot_clips(json_file, game_dir, output_dir, game_name):
    """
    Extract 15-second clips of shots on target that didn't result in goals.
    
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

    # Sort all events by position to get chronological order
    sorted_events = sorted(annotations, key=lambda x: int(x.get('position', 0)))
    
    # Extract goal events to avoid them
    goal_events = []
    for event in sorted_events:
        if event.get('label') == 'Goal':
            try:
                period = int(event['gameTime'].split(' - ')[0])
                time_str = event['gameTime'].split(' - ')[1]
                minutes, seconds = map(int, time_str.split(':'))
                # Convert to total seconds from start of period
                total_seconds = minutes * 60 + seconds
                goal_events.append((period, total_seconds))
            except (KeyError, ValueError, IndexError):
                continue
    
    # Find shots on target that didn't result in goals
    shot_events = []
    for event in sorted_events:
        if event.get('label') == 'Shots on target':
            try:
                period = int(event['gameTime'].split(' - ')[0])
                time_str = event['gameTime'].split(' - ')[1]
                minutes, seconds = map(int, time_str.split(':'))
                team = event.get('team', 'unknown')
                position = int(event.get('position', 0))
                
                # Check if this shot is close to a goal (within 10 seconds)
                is_near_goal = False
                shot_time = minutes * 60 + seconds
                
                for goal_period, goal_time in goal_events:
                    if period == goal_period:
                        time_diff = abs(goal_time - shot_time)
                        if time_diff < 10:  # Within 10 seconds of a goal
                            is_near_goal = True
                            break
                
                # Only include shots that aren't near goals
                if not is_near_goal:
                    shot_events.append({
                        'period': period,
                        'minutes': minutes,
                        'seconds': seconds,
                        'team': team,
                        'position': position,
                        'gameTime': event['gameTime']
                    })
            except (KeyError, ValueError, IndexError) as e:
                print(f"Error processing shot event: {e}")
                continue
    
    print(f"Game: {game_name} - Found {len(shot_events)} shots on target (excluding those near goals)")
    if len(shot_events) == 0:
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
    
    # Process each shot event
    for i, shot in enumerate(shot_events):
        try:
            period = shot['period']
            minutes = shot['minutes']
            seconds = shot['seconds']
            team = shot['team']
            
            # Select correct video file based on period
            if period <= 0 or period > 2:
                print(f"Error: Invalid period {period} for shot at {shot['gameTime']}")
                continue
                
            video_path = video_files[period - 1]
            if video_path is None:
                print(f"Error: Video file for period {period} not available. Skipping shot at {shot['gameTime']}")
                continue
            
            # Extract the clip
            time_str = f"{minutes:02d}:{seconds:02d}"
            clip_name = f"{game_name}_shot_{i+1}_period{period}_{time_str.replace(':', 'm')}s_{team}.mkv"
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
            
            # Convert shot time to seconds from the beginning of the half
            minutes_in_seconds = minutes * 60
            total_seconds = minutes_in_seconds + seconds
            shot_frame = int(total_seconds * fps)
            
            # Calculate start frame (15 seconds that include the shot)
            # Start 10 seconds before the shot and continue 5 seconds after
            seconds_before = 10
            seconds_after = 5
            start_frame = max(0, shot_frame - (seconds_before * int(fps)))
            duration = seconds_before + seconds_after  # 15 seconds total
            
            # Calculate time values for ffmpeg
            start_time = start_frame / fps
            
            # Use ffmpeg to extract the clip
            ffmpeg_cmd = "ffmpeg"
            
            # Try copy mode first (faster, no re-encoding)
            cmd = [
                ffmpeg_cmd,
                "-i", video_path,
                "-ss", f"{start_time:.3f}",
                "-t", f"{duration:.3f}",
                "-c", "copy",       # Copy the codec (no re-encoding)
                "-y",               # Overwrite output files without asking
                output_path
            ]
            
            print(f"Extracting shot {i+1}: {shot['gameTime']} - {team} team")
            
            try:
                # On Linux (cluster), we don't need shell=True
                # Capture stderr for debugging
                result = subprocess.run(cmd, check=False, stderr=subprocess.PIPE)
                
                # Check if the command succeeded
                if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    print(f"Successfully saved clip to {output_path}")
                else:
                    # If the copy method fails, try re-encoding method for more accuracy
                    print(f"Copy method failed. Trying with re-encoding...")
                    # For better accuracy with re-encoding, put -ss after input
                    fallback_cmd = [
                        ffmpeg_cmd,
                        "-i", video_path,
                        "-ss", f"{start_time:.3f}",
                        "-t", f"{duration:.3f}",
                        "-c:v", "libx264",  # Use x264 codec
                        "-c:a", "aac",      # Use AAC for audio
                        "-strict", "experimental",
                        "-b:v", "2500k",    # Reasonable bitrate
                        "-preset", "fast",  # Faster encoding with good quality
                        "-y",               # Overwrite output files
                        output_path
                    ]
                    
                    fallback_result = subprocess.run(fallback_cmd, check=False, stderr=subprocess.PIPE)
                    
                    if fallback_result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        print(f"Successfully saved clip using re-encoding to {output_path}")
                    else:
                        print(f"Error extracting clip: {fallback_result.stderr.decode()}")
                        # Try one last method with different codec options
                        last_cmd = [
                            ffmpeg_cmd,
                            "-i", video_path,
                            "-ss", f"{start_time:.3f}",
                            "-t", f"{duration:.3f}",
                            "-vcodec", "mpeg4",
                            "-q:v", "5",
                            "-acodec", "aac",
                            "-y",
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
                
        except (KeyError, ValueError, IndexError) as e:
            print(f"Error processing shot event: {e}")
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