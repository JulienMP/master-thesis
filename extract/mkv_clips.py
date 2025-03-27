import os
import json
import subprocess

# Paths
CODE_DIR = os.getcwd()  # Get current working directory
DATA_DIR = os.path.join(CODE_DIR, "data_of_interest")
OUTPUT_DIR = os.path.join(CODE_DIR, "extracted")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Check FFmpeg capabilities
def get_ffmpeg_version():
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE,
                              text=True)
        return result.stdout
    except Exception as e:
        return f"Error checking FFmpeg: {str(e)}"

print(f"FFmpeg version info:")
print(get_ffmpeg_version().split('\n')[0])

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

# Extract clips function with basic FFmpeg command
def extract_clips(game_path):
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
    
    # Filter out offside goals
    valid_goals = [event for event in data["annotations"] if event["label"] == "Goal"]
    offside_positions = {e["position"] for e in data["annotations"] if e["label"] == "Offside"}
    valid_goals = [goal for goal in valid_goals if goal["position"] not in offside_positions]
    
    print(f"  Found {len(valid_goals)} valid goals")
    
    for i, goal in enumerate(valid_goals):
        try:
            # Parse position and calculate timestamps
            position = int(goal["position"])
            timestamp = position / 25  # Assuming 25 FPS
            start_time = max(0, timestamp - 15)  # 15 seconds before goal
            duration = 30  # 15 seconds before + 15 seconds after
            
            # Get the half information
            half = int(goal["gameTime"].split(" - ")[0])
            video_file = os.path.join(game_path, f"{half}_224p.mkv")
            
            if not os.path.exists(video_file):
                print(f"  Video file not found: {video_file}")
                continue

            # Create descriptive output filename
            game_name = os.path.basename(game_path)
            output_file = os.path.join(OUTPUT_DIR, f"{game_name}_goal{i+1}_pos{position}.mkv")
            
            # Format start time for FFmpeg (HH:MM:SS.mmm)
            hours = int(start_time // 3600)
            minutes = int((start_time % 3600) // 60)
            seconds = start_time % 60
            start_time_str = f"{hours:02d}:{minutes:02d}:{seconds:.3f}"
            
            print(f"  Extracting Goal {i+1}: {start_time_str} for {duration}s from {video_file}")
            
            # Method 1: Simplest approach - try direct copy first
            try:
                # Simple copy without re-encoding (fastest if it works)
                copy_cmd = [
                    'ffmpeg',
                    '-y',  # Overwrite output files
                    '-ss', start_time_str,  # Start time
                    '-i', video_file,  # Input file
                    '-t', str(duration),  # Duration
                    '-c', 'copy',  # Just copy streams without re-encoding
                    output_file
                ]
                
                print(f"  Attempting direct stream copy...")
                copy_result = subprocess.run(copy_cmd, 
                                           stdout=subprocess.PIPE, 
                                           stderr=subprocess.PIPE,
                                           text=True)
                
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    print(f"  Success! Extracted clip saved to {output_file}")
                    continue  # Skip to next clip if successful
                else:
                    print(f"  Direct copy failed, will try re-encoding...")
            except Exception as e:
                print(f"  Direct copy error: {str(e)}")
            
            # Method 2: If direct copy failed, try re-encoding with minimal options
            try:
                # Re-encode with minimal options (more compatible)
                encode_cmd = [
                    'ffmpeg',
                    '-y',  # Overwrite output files
                    '-ss', start_time_str,  # Start time
                    '-i', video_file,  # Input file
                    '-t', str(duration),  # Duration
                    output_file
                ]
                
                print(f"  Attempting with minimal re-encoding...")
                encode_result = subprocess.run(encode_cmd, 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.PIPE,
                                             text=True)
                
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    print(f"  Success! Extracted clip saved to {output_file}")
                    continue  # Skip to next clip if successful
                else:
                    print(f"  Re-encoding failed. Error: {encode_result.stderr}")
            except Exception as e:
                print(f"  Re-encoding error: {str(e)}")
            
            # Method 3: If all else fails, try with different container format (MP4)
            try:
                # Try with MP4 container which has better compatibility
                mp4_output = os.path.join(OUTPUT_DIR, f"{game_name}_goal{i+1}_pos{position}.mp4")
                mp4_cmd = [
                    'ffmpeg',
                    '-y',  # Overwrite output files
                    '-ss', start_time_str,  # Start time
                    '-i', video_file,  # Input file
                    '-t', str(duration),  # Duration
                    mp4_output
                ]
                
                print(f"  Attempting with MP4 format...")
                mp4_result = subprocess.run(mp4_cmd, 
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE,
                                          text=True)
                
                if os.path.exists(mp4_output) and os.path.getsize(mp4_output) > 0:
                    print(f"  Success! Extracted clip saved to {mp4_output}")
                    continue  # Skip to next clip if successful
                else:
                    print(f"  MP4 extraction failed. Error: {mp4_result.stderr}")
            except Exception as e:
                print(f"  MP4 format error: {str(e)}")
            
            print(f"  All extraction methods failed for this clip.")
                
        except Exception as e:
            print(f"  Error processing goal at position {goal['position']}: {e}")

# Main execution
print(f"Searching for game directories in {DATA_DIR}...")
game_paths = find_game_paths(limit=10)
print(f"Found {len(game_paths)} game directories")

for i, game_path in enumerate(game_paths):
    print(f"Processing game {i+1}/{len(game_paths)}: {os.path.basename(game_path)}")
    extract_clips(game_path)

print("\nProcessing complete.")