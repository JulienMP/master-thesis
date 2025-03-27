import os
import json
import glob
import cv2

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
        
        # OpenCV video processing
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            print(f"  Error opening video file: {video_file}")
            continue
            
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        start_frame = int(start_time * fps)
        end_frame = start_frame + (15 * fps)
        
        # Try XVID codec which is more commonly available
        fourcc = cv2.VideoWriter_fourcc(*'XVID')  
        # Change output file extension to match codec
        output_file = output_file.replace('.mkv', '.avi')
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or cap.get(cv2.CAP_PROP_POS_FRAMES) > end_frame:
                break
            out.write(frame)
            frame_count += 1
        
        cap.release()
        out.release()
        
        # Check if file was created and has content
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"  Successfully extracted: {output_file} ({frame_count} frames)")
        else:
            print(f"  Failed to create: {output_file} - Check codec availability")
            
            # Print available codecs for debugging
            print("  Available codecs in your OpenCV installation:")
            fourcc_list = [
                'XVID', 'MJPG', 'MP4V', 'MPG4', 'DIV3', 'DIVX', 'H264', 
                'AVC1', 'WMV1', 'WMV2', 'FMP4', 'MPEG', 'IYUV', 'I420'
            ]
            
            # Test codec availability
            available_codec = None
            for codec in fourcc_list:
                temp_file = os.path.join(OUTPUT_DIR, f"test_{codec}.avi")
                test_writer = cv2.VideoWriter(
                    temp_file, 
                    cv2.VideoWriter_fourcc(*codec), 
                    25, 
                    (320, 240)
                )
                if test_writer.isOpened():
                    test_writer.release()
                    os.remove(temp_file)
                    print(f"    - {codec}: Available")
                    available_codec = codec
                else:
                    print(f"    - {codec}: Not available")
            
            # If a codec is available, try again with that codec
            if available_codec:
                print(f"  Trying again with {available_codec} codec...")
                frame_folder = os.path.join(OUTPUT_DIR, os.path.basename(output_file).replace('.avi', ''))
                os.makedirs(frame_folder, exist_ok=True)
                
                # Retry with available codec
                output_file_retry = output_file.replace('.avi', f'_{available_codec}.avi')
                retry_fourcc = cv2.VideoWriter_fourcc(*available_codec)
                retry_out = cv2.VideoWriter(output_file_retry, retry_fourcc, fps, (width, height))
                
                cap = cv2.VideoCapture(video_file)
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                frame_count = 0
                
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret or cap.get(cv2.CAP_PROP_POS_FRAMES) > end_frame:
                        break
                    retry_out.write(frame)
                    
                    # Also save as image
                    frame_path = os.path.join(frame_folder, f"frame_{frame_count:04d}.jpg")
                    cv2.imwrite(frame_path, frame)
                    
                    frame_count += 1
                
                cap.release()
                retry_out.release()
                
                if os.path.exists(output_file_retry) and os.path.getsize(output_file_retry) > 0:
                    print(f"  Successfully extracted with {available_codec}: {output_file_retry} ({frame_count} frames)")
                else:
                    print(f"  Extraction failed with all codecs. Saved {frame_count} frames as images in {frame_folder}")

# Loop through selected games
for game in game_paths:
    extract_clips(game)

print("Processing complete.")