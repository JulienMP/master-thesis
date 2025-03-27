import os
import json
import glob
import cv2

# Paths
CODE_DIR = os.path.expanduser("~/Code")
DATA_DIR = os.path.join(CODE_DIR, "data_of_interest")
OUTPUT_DIR = os.path.join(CODE_DIR, "before_goal")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Get 10 game directories
all_games = glob.glob(os.path.join(DATA_DIR, "*/**/*"))[:10]

# Process each game
def extract_clips(game_path):
    json_path = os.path.join(game_path, "Labels-v2.json")
    if not os.path.exists(json_path):
        return

    with open(json_path, "r") as f:
        data = json.load(f)
    
    # Filter out offside goals
    valid_goals = [event for event in data["annotations"] if event["label"] == "Goal"]
    offside_positions = {e["position"] for e in data["annotations"] if e["label"] == "Offside"}
    valid_goals = [goal for goal in valid_goals if goal["position"] not in offside_positions]
    
    for goal in valid_goals:
        timestamp = int(goal["position"]) / 25  # Assuming 25 FPS
        start_time = max(0, timestamp - 15)
        half = int(goal["gameTime"].split(" - ")[0])
        video_file = os.path.join(game_path, f"{half}_224p.mkv")
        if not os.path.exists(video_file):
            continue

        output_file = os.path.join(OUTPUT_DIR, f"{os.path.basename(game_path)}_{goal['position']}.mkv")
        
        # OpenCV video processing
        cap = cv2.VideoCapture(video_file)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        start_frame = int(start_time * fps)
        end_frame = start_frame + (15 * fps)
        
        fourcc = cv2.VideoWriter_fourcc(*'X264')  # MKV uses H.264 encoding
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or cap.get(cv2.CAP_PROP_POS_FRAMES) > end_frame:
                break
            out.write(frame)
        
        cap.release()
        out.release()
        print(f"Extracted: {output_file}")

# Loop through selected games
for game in all_games:
    extract_clips(game)

print("Processing complete.")
