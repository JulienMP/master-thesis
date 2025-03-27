import os
import json
import subprocess

# Paths
CODE_DIR = os.getcwd()  # Current working directory
DATA_DIR = os.path.join(CODE_DIR, "data_of_interest")
OUTPUT_DIR = os.path.join(CODE_DIR, "before_goal")
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

# Extract goal clips with minimal FFmpeg options
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
            duration = 15.0
            start_time = max(0, timestamp - duration)
            
            # Get half information
            half = int(goal["gameTime"].split(" - ")[0])
            video_file = os.path.join(game_path, f"{half}_224p.mkv")
            
            if not os.path.exists(video_file):
                print(f"  Video file not found: {video_file}")
                continue

            # Create descriptive output filename
            game_name = os.path.basename(game_path)
            teams = f"{data.get('gameHomeTeam', '')}_{data.get('gameAwayTeam', '')}"
            
            # Try both MP4 and MKV formats
            output_file = os.path.join(OUTPUT_DIR, f"{game_name}_goal{i+1}_{teams}.mp4")
            
            # Format start time for FFmpeg
            hours = int(start_time // 3600)
            minutes = int((start_time % 3600) // 60)
            seconds = start_time % 60
            start_time_str = f"{hours:02d}:{minutes:02d}:{seconds:.3f}"
            
            print(f"  Extracting Goal {i+1}: {duration}s before position {position}")
            print(f"  From: {video_file}")
            print(f"  Starting at: {start_time_str}")
            
            # Use absolutely minimal FFmpeg command that should work with any version
            cmd = [
                'ffmpeg',
                '-y',                # Overwrite output
                '-ss', start_time_str,  # Start position
                '-i', video_file,    # Input file
                '-t', str(duration), # Duration - exactly 15 seconds
                '-c', 'copy',        # Just copy streams without re-encoding
                output_file
            ]
            
            print(f"  Running: {' '.join(cmd)}")
            
            # Run FFmpeg
            result = subprocess.run(cmd, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  text=True)
            
            # Check if extraction succeeded
            if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:  # At least 1KB
                print(f"  Success! Clip saved to: {output_file}")
            else:
                # If copy fails, try fallback method with no specific codec
                print(f"  Direct copy failed, trying simpler encoding...")
                
                # Fallback to even simpler command
                fallback_file = os.path.join(OUTPUT_DIR, f"{game_name}_goal{i+1}_{teams}_fallback.mp4")
                fallback_cmd = [
                    'ffmpeg',
                    '-y',                # Overwrite output
                    '-ss', start_time_str,  # Start position
                    '-i', video_file,    # Input file
                    '-t', str(duration), # Duration - exactly 15 seconds
                    fallback_file
                ]
                
                print(f"  Running fallback: {' '.join(fallback_cmd)}")
                
                fallback_result = subprocess.run(fallback_cmd, 
                                               stdout=subprocess.PIPE, 
                                               stderr=subprocess.PIPE,
                                               text=True)
                
                if os.path.exists(fallback_file) and os.path.getsize(fallback_file) > 1000:
                    print(f"  Success with fallback method! Clip saved to: {fallback_file}")
                else:
                    print(f"  All extraction methods failed for this clip.")
                    print(f"  FFmpeg error: {fallback_result.stderr}")
                
        except Exception as e:
            print(f"  Error processing goal: {str(e)}")

# Main execution
print("Starting goal clip extraction...")
game_paths = find_game_paths(limit=10)
print(f"Found {len(game_paths)} game directories")

for i, game_path in enumerate(game_paths):
    print(f"Processing game {i+1}/{len(game_paths)}: {os.path.basename(game_path)}")
    extract_goal_clips(game_path)

print("\nProcessing complete!")