import os
import json
import glob
import cv2
import subprocess
import tempfile
import shutil

# Check if FFmpeg is installed
def is_ffmpeg_available():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

# Print FFmpeg availability
if is_ffmpeg_available():
    print("FFmpeg is available - using it for MKV extraction")
else:
    print("WARNING: FFmpeg is not installed. This script will try to use OpenCV as fallback, but MKV creation may fail.")
    print("For best results, please install FFmpeg: https://ffmpeg.org/download.html")

# Paths
# Use current directory instead of assuming path
CODE_DIR = os.getcwd()  # Get current working directory
DATA_DIR = os.path.join(CODE_DIR, "data_of_interest")
OUTPUT_DIR = os.path.join(CODE_DIR, "before_goal")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Correct path structure based on your directory layout
# This will find all the game directories in the correct structure
game_paths = []
leagues = os.listdir(DATA_DIR)
for league in leagues:
    league_path = os.path.join(DATA_DIR, league)
    if os.path.isdir(league_path):
        seasons = os.listdir(league_path)
        for season in seasons:
            season_path = os.path.join(league_path, season)
            if os.path.isdir(season_path):
                games = os.listdir(season_path)
                for game in games:
                    game_path = os.path.join(season_path, game)
                    if os.path.isdir(game_path):
                        game_paths.append(game_path)

# Get 10 game directories
game_paths = game_paths[:10]
print(f"Found {len(game_paths)} game directories")
for path in game_paths:
    print(f"  - {path}")

# Process each game
def extract_clips(game_path):
    json_path = os.path.join(game_path, "Labels-v2.json")
    if not os.path.exists(json_path):
        print(f"No Labels-v2.json found in {game_path}")
        return

    print(f"Processing game: {game_path}")
    with open(json_path, "r") as f:
        data = json.load(f)
    
    # Filter out offside goals
    valid_goals = [event for event in data["annotations"] if event["label"] == "Goal"]
    offside_positions = {e["position"] for e in data["annotations"] if e["label"] == "Offside"}
    valid_goals = [goal for goal in valid_goals if goal["position"] not in offside_positions]
    
    print(f"  Found {len(valid_goals)} valid goals")
    
    for goal in valid_goals:
        timestamp = int(goal["position"]) / 25  # Assuming 25 FPS
        start_time = max(0, timestamp - 15)
        half = int(goal["gameTime"].split(" - ")[0])
        video_file = os.path.join(game_path, f"{half}_224p.mkv")
        
        if not os.path.exists(video_file):
            print(f"  Video file not found: {video_file}")
            continue

        output_file = os.path.join(OUTPUT_DIR, f"{os.path.basename(game_path)}_{goal['position']}.mkv")
        
        # Use FFmpeg for extraction instead of OpenCV VideoWriter
        # First, create a temporary directory for frame extraction
        import tempfile
        import subprocess
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        frames_dir = os.path.join(temp_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Calculate timestamps
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            print(f"  Error opening video file: {video_file}")
            continue
            
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        start_frame = int(start_time * fps)
        end_frame = start_frame + (15 * fps)
        duration = 15  # seconds
        
        # Calculate start time in HH:MM:SS.mmm format for ffmpeg
        start_seconds = start_time
        start_time_str = f"{int(start_seconds//3600):02d}:{int((start_seconds%3600)//60):02d}:{start_seconds%60:.3f}"
        
        # Close the OpenCV capture
        cap.release()
        
        print(f"  Extracting from {video_file} starting at {start_time_str} for {duration} seconds")
        
        # Try direct FFmpeg extraction first (most efficient)
        try:
            # Extract clip directly using FFmpeg
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', video_file,
                '-ss', start_time_str,
                '-t', str(duration),
                '-c:v', 'copy',  # Copy video stream without re-encoding
                '-c:a', 'copy',  # Copy audio stream without re-encoding
                output_file
            ]
            
            print(f"  Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
            subprocess.run(ffmpeg_cmd, check=True, stderr=subprocess.PIPE)
            
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f"  Successfully extracted: {output_file} using FFmpeg")
                frame_count = end_frame - start_frame
                continue  # Skip to next clip if successful
            else:
                print(f"  Direct extraction failed, trying re-encoding approach...")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  FFmpeg direct extraction failed: {str(e)}")
        
        # Fallback: Extract frames with OpenCV and reassemble with FFmpeg
        try:
            # Extract frames with OpenCV
            cap = cv2.VideoCapture(video_file)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            frame_count = 0
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret or cap.get(cv2.CAP_PROP_POS_FRAMES) > end_frame:
                    break
                
                # Save frame as image
                frame_path = os.path.join(frames_dir, f"frame_{frame_count:06d}.jpg")
                cv2.imwrite(frame_path, frame)
                frame_count += 1
            
            cap.release()
            
            if frame_count > 0:
                # Create video from frames using FFmpeg
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-framerate', str(fps),
                    '-i', os.path.join(frames_dir, 'frame_%06d.jpg'),
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    output_file
                ]
                
                print(f"  Reassembling {frame_count} frames with FFmpeg")
                subprocess.run(ffmpeg_cmd, check=True, stderr=subprocess.PIPE)
                
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    print(f"  Successfully created: {output_file} from {frame_count} frames")
                else:
                    print(f"  Failed to create video from frames")
            else:
                print(f"  No frames were extracted")
                
        except Exception as e:
            print(f"  Error in fallback extraction: {str(e)}")
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"  Warning: Could not clean up temp directory: {str(e)}")
        
        # Final check (moved to after all extraction attempts in the new code)
        # If the file wasn't created by any method, create a directory with the frames
        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            print(f"  All extraction methods failed for {output_file}")
            
            # Create a directory for individual frames as last resort
            frames_dir = os.path.join(OUTPUT_DIR, os.path.basename(output_file).replace('.mkv', '_frames'))
            os.makedirs(frames_dir, exist_ok=True)
            
            cap = cv2.VideoCapture(video_file)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            frame_count = 0
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret or cap.get(cv2.CAP_PROP_POS_FRAMES) > end_frame:
                    break
                
                # Save frame as image
                frame_path = os.path.join(frames_dir, f"frame_{frame_count:04d}.jpg")
                cv2.imwrite(frame_path, frame)
                frame_count += 1
            
            cap.release()
            
            print(f"  Saved {frame_count} individual frames to {frames_dir}")

# Loop through selected games
for game in game_paths:
    extract_clips(game)

print("Processing complete.")