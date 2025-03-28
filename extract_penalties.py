import json
import os
import cv2
import subprocess
import glob
import argparse
from pathlib import Path

def extract_penalty_clips(json_file, game_dir, output_dir, game_name):
    """
    Extract 15-second clips before penalties from football match videos.
    
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

    # Extract penalty events
    penalty_events = []
    
    # Look for penalty annotations directly
    penalty_events.extend([event for event in annotations if event.get('label') == 'Penalty'])
    
    # If no penalties are found, look for fouls that might have led to penalties
    # We'll analyze the events to see if a foul is followed by a penalty kick
    if len(penalty_events) == 0:
        # Sort all annotations by position to get chronological order
        sorted_events = sorted(annotations, key=lambda x: int(x.get('position', 0)))
        
        for i, event in enumerate(sorted_events[:-1]):  # Check all events except the last one
            if event.get('label') == 'Foul':
                # Look for a penalty kick or direct free-kick in the next few events
                for j in range(1, min(5, len(sorted_events) - i)):  # Check next 5 events
                    next_event = sorted_events[i + j]
                    if next_event.get('label') in ['Penalty', 'Direct free-kick']:
                        # This foul likely led to a penalty
                        penalty_events.append(event)
                        break
    
    print(f"Game: {game_name} - Found {len(penalty_events)} penalty/foul events")
    if len(penalty_events) == 0:
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
    
    # Process each penalty event
    for i, penalty in enumerate(penalty_events):
        try:
            # Extract information from the penalty event
            period = int(penalty['gameTime'].split(' - ')[0])
            time_str = penalty['gameTime'].split(' - ')[1]
            minutes, seconds = map(int, time_str.split(':'))
            team = penalty.get('team', 'unknown')
            penalty_type = penalty.get('label', 'unknown')
            
            # Select correct video file based on period
            if period <= 0 or period > 2:
                print(f"Error: Invalid period {period} for event at {penalty['gameTime']}")
                continue
                
            video_path = video_files[period - 1]
            if video_path is None:
                print(f"Error: Video file for period {period} not available. Skipping event at {penalty['gameTime']}")
                continue
            
            # Extract the clip
            clip_name = f"{game_name}_penalty_{i+1}_period{period}_{time_str.replace(':', 'm')}s_{team}_{penalty_type}.mkv"
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
            
            # Convert penalty time to seconds from the beginning of the half
            minutes_in_seconds = minutes * 60
            total_seconds = minutes_in_seconds + seconds
            penalty_frame = int(total_seconds * fps)
            
            # Calculate start frame (15 seconds before penalty)
            # This should include the foul that led to the penalty
            seconds_to_extract = 15
            start_frame = max(0, penalty_frame - (seconds_to_extract * int(fps)))
            
            # Calculate time values for ffmpeg
            start_time = start_frame / fps
            duration = seconds_to_extract  # Exactly 15 seconds
            
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
            
            print(f"Extracting penalty {i+1}: {penalty['gameTime']} - {team} team - {penalty_type}")
            
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
                        # Try one last method - just skip the problematic part
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
            print(f"Error processing penalty event: {e}")
            continue

def process_all_games(data_dir, output_dir):
    """
    Process all games in the data directory and extract penalty clips.
    
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
            extract_penalty_clips(json_file, game_dir, output_dir, game_name)
        else:
            print(f"Warning: No Labels-v2.json file found in {game_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract penalty clips from football games.')
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