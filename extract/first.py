
import os
import json
import cv2
import numpy as np

# Paths
CODE_DIR = os.getcwd()  # Current working directory
DATA_DIR = os.path.join(CODE_DIR, "data_of_interest")
OUTPUT_DIR = os.path.join(CODE_DIR, "first")
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Files will be saved to: {OUTPUT_DIR}")

# Find game paths
def find_game_paths(limit=10):
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
                            if len(game_paths) >= limit:
                                return game_paths
    return game_paths

# Extract goal clips using OpenCV
def extract_goal_clips(game_path):
    json_path = os.path.join(game_path, "Labels-v2.json")
    if not os.path.exists(json_path):
        print(f"No Labels-v2.json found in {game_path}")
        return

    print(f"\nProcessing game: {game_path}")
    
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON file {json_path}")
        return
    
    # Get all goals
    goals = [event for event in data["annotations"] if event["label"] == "Goal"]
    
    print(f"  Found {len(goals)} goals")
    
    for i, goal in enumerate(goals):
        try:
            # Get time information
            position = int(goal["position"])
            timestamp = position / 25  # Assuming 25 FPS
            
            # Extract 15 seconds before the goal
            duration_sec = 15.0
            start_time = max(0, timestamp - duration_sec)
            
            # Get half information
            half = int(goal["gameTime"].split(" - ")[0])
            video_file = os.path.join(game_path, f"{half}_224p.mkv")
            
            if not os.path.exists(video_file):
                print(f"  Video file not found: {video_file}")
                continue

            # Create descriptive output filename
            game_name = os.path.basename(game_path)
            teams = f"{data.get('gameHomeTeam', '')}_{data.get('gameAwayTeam', '')}"
            output_file = os.path.join(OUTPUT_DIR, f"{game_name}_goal{i+1}_{teams}.avi")
            
            print(f"  Extracting Goal {i+1}: {duration_sec}s before position {position}")
            print(f"  From: {video_file}")
            print(f"  Output: {output_file}")
            
            # Open the video file
            cap = cv2.VideoCapture(video_file)
            if not cap.isOpened():
                print(f"  Error: Could not open video file {video_file}")
                continue
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calculate frame positions
            start_frame = int(start_time * fps)
            duration_frames = int(duration_sec * fps)
            end_frame = start_frame + duration_frames
            
            print(f"  FPS: {fps}, Start frame: {start_frame}, Frames to capture: {duration_frames}")
            
            # Set up the video writer - try multiple codecs until one works
            fourcc_options = [
                cv2.VideoWriter_fourcc(*'XVID'),  # Most compatible
                cv2.VideoWriter_fourcc(*'MJPG'),  # Motion JPEG
                cv2.VideoWriter_fourcc(*'DIVX'),  # DivX
                cv2.VideoWriter_fourcc(*'MP4V')   # MP4
            ]
            
            # Try different codecs until one works
            out = None
            for fourcc in fourcc_options:
                codec_name = ''.join([chr((fourcc >> 8*i) & 0xFF) for i in range(4)])
                temp_output = output_file.replace('.avi', f'_{codec_name}.avi')
                print(f"  Trying codec: {codec_name}")
                
                out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
                if out.isOpened():
                    print(f"  Found working codec: {codec_name}")
                    output_file = temp_output  # Use this filename
                    break
                else:
                    out.release()
                    if os.path.exists(temp_output):
                        os.remove(temp_output)
            
            if not out or not out.isOpened():
                print(f"  Error: Could not find a working codec for video writing")
                cap.release()
                continue
            
            # Set the position to start frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # Read and write frames
            frames_written = 0
            while cap.isOpened() and frames_written < duration_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                out.write(frame)
                frames_written += 1
                
                # Show progress every 50 frames
                if frames_written % 50 == 0:
                    print(f"  Progress: {frames_written}/{duration_frames} frames ({frames_written/duration_frames*100:.1f}%)")
            
            # Release resources
            cap.release()
            out.release()
            
            # Check if file was created successfully
            if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:  # At least 1KB
                print(f"  Success! Wrote {frames_written} frames to {output_file}")
                
                # Try to verify the duration using OpenCV
                verify_cap = cv2.VideoCapture(output_file)
                if verify_cap.isOpened():
                    verify_frames = int(verify_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    verify_fps = verify_cap.get(cv2.CAP_PROP_FPS)
                    verify_duration = verify_frames / verify_fps if verify_fps > 0 else 0
                    verify_cap.release()
                    
                    print(f"  Verification: Clip contains {verify_frames} frames, {verify_duration:.2f} seconds at {verify_fps} fps")
                    
                    if verify_frames < duration_frames * 0.9:  # Less than 90% of expected frames
                        print(f"  Warning: Clip may be shorter than expected ({verify_frames} < {duration_frames})")
            else:
                print(f"  Error: Failed to create clip or file is too small")
                
                # Fallback: Save individual frames as images
                print(f"  Fallback: Saving individual frames as images")
                frames_dir = os.path.join(OUTPUT_DIR, f"{game_name}_goal{i+1}_{teams}_frames")
                os.makedirs(frames_dir, exist_ok=True)
                
                cap = cv2.VideoCapture(video_file)
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                
                frames_saved = 0
                while cap.isOpened() and frames_saved < duration_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    frame_path = os.path.join(frames_dir, f"frame_{frames_saved:04d}.jpg")
                    cv2.imwrite(frame_path, frame)
                    frames_saved += 1
                
                cap.release()
                print(f"  Saved {frames_saved} frames to {frames_dir}")
                
        except Exception as e:
            print(f"  Error processing goal: {str(e)}")

# Main execution
print("Starting goal clip extraction using OpenCV...")
game_paths = find_game_paths(limit=10)
print(f"Found {len(game_paths)} game directories")

for i, game_path in enumerate(game_paths):
    print(f"Processing game {i+1}/{len(game_paths)}: {os.path.basename(game_path)}")
    extract_goal_clips(game_path)

print("\nProcessing complete!")