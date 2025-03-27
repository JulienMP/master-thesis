import os
import json
import glob
import subprocess

# ffmpeg needs to be installed for video processing
# Paths
CODE_DIR = os.path.expanduser("~/Code")
DATA_DIR = os.path.join(CODE_DIR, "data_of_interest")
OUTPUT_DIR = os.path.join(CODE_DIR, "before_goal")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Get 10 game directories
all_games = glob.glob(os.path.join(DATA_DIR, "*/**/*"))[:10]  # Adjust based on structure

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

        output_file = os.path.join(OUTPUT_DIR, f"{os.path.basename(game_path)}_{goal['position']}.mp4")
        command = [
            "ffmpeg", "-i", video_file, "-ss", str(start_time), "-t", "15", "-c:v", "libx264", "-c:a", "aac", output_file
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Extracted: {output_file}")

# Loop through selected games
for game in all_games:
    extract_clips(game)

print("Processing complete.")
