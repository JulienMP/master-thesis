import json
import os
import argparse
import glob
import shutil

def find_directories_with_penalty(data_dir, output_txt_file, labels_dir):
    """
    Searches for 'Labels-v2.json' files within subdirectories of data_dir,
    checks for a 'Penalty' label within the annotations, writes the paths
    of directories containing such labels to a text file, and copies
    the Labels-v2.json files to the specified labels_dir.
    
    Args:
        data_dir (str): The root directory containing game subdirectories.
        output_txt_file (str): The path to the output text file to create.
        labels_dir (str): The directory to copy the Labels-v2.json files to.
    """
    # Create the labels directory if it doesn't exist
    os.makedirs(labels_dir, exist_ok=True)
    
    penalty_dirs = set()  # Use a set to automatically handle duplicates
    
    # Use glob to find all Labels-v2.json files efficiently
    json_pattern = os.path.join(data_dir, "*", "Labels-v2.json")
    print(f"Searching for JSON files matching: {json_pattern}")
    json_files_found = glob.glob(json_pattern)
    print(f"Found {len(json_files_found)} potential 'Labels-v2.json' files.")
    
    if not json_files_found:
        # Fallback to os.walk if glob doesn't find files (e.g., deeper structure)
        print("Glob found no files, trying os.walk (might be slower)...")
        for root, dirs, files in os.walk(data_dir):
            if "Labels-v2.json" in files:
                json_files_found.append(os.path.join(root, "Labels-v2.json"))
        print(f"Found {len(json_files_found)} potential 'Labels-v2.json' files via os.walk.")
    
    for json_file_path in json_files_found:
        game_dir = os.path.dirname(json_file_path)  # Get the directory containing the JSON
        game_name = os.path.basename(game_dir)
        
        try:
            with open(json_file_path, 'r') as f:
                data = json.load(f)
            
            annotations = data.get('annotations', [])
            if not annotations:
                continue
            
            # Since there is no "Penalty" label, we'll look for patterns
            # that suggest penalties: Fouls followed by Direct free-kicks
            
            # Sort events by position to get chronological order
            sorted_events = sorted(annotations, key=lambda x: int(x.get('position', 0)))
            found_potential_penalty = False
            
            for i, event in enumerate(sorted_events[:-2]):  # Check all events except the last two
                # Only consider fouls
                if event.get('label') == 'Foul':
                    team_fouled = event.get('team', 'unknown')  # Team that committed the foul
                    
                    # The team taking the free-kick would be the opposite team
                    team_taking_kick = 'home' if team_fouled == 'away' else 'away'
                    
                    # Check next few events (up to 5 events forward)
                    for j in range(1, min(5, len(sorted_events) - i)):
                        next_event = sorted_events[i + j]
                        
                        # Check if it's a direct free-kick
                        if next_event.get('label') == 'Direct free-kick':
                            # Check if it's the correct team taking the kick (opposite of fouling team)
                            if next_event.get('team') == team_taking_kick:
                                # This might be a penalty - check for shot or goal within the next few events
                                shots_or_goals = False
                                for k in range(1, min(3, len(sorted_events) - i - j)):
                                    follow_event = sorted_events[i + j + k]
                                    follow_label = follow_event.get('label', '')
                                    if follow_label in ['Shots on target', 'Shots off target', 'Goal']:
                                        shots_or_goals = True
                                        break
                                
                                if shots_or_goals:
                                    # This pattern strongly suggests a penalty
                                    penalty_dirs.add(game_dir)
                                    found_potential_penalty = True
                                    
                                    # Copy the Labels-v2.json file to the labels directory
                                    output_file = os.path.join(labels_dir, f"{game_name}_Labels-v2.json")
                                    shutil.copy2(json_file_path, output_file)
                                    print(f"Copied {json_file_path} to {output_file}")
                                    
                                    break  # Found a likely penalty, move to the next file
                        
                    if found_potential_penalty:
                        break  # No need to check more events in this file
                
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON in file: {json_file_path}")
        except FileNotFoundError:
            print(f"Warning: File not found (should not happen): {json_file_path}")
        except Exception as e:
            print(f"Warning: An unexpected error occurred processing {json_file_path}: {e}")
    
    # Write the found directories to the output file
    print(f"\nFound {len(penalty_dirs)} directories containing potential penalty situations.")
    try:
        with open(output_txt_file, 'w') as f_out:
            # Sort directories alphabetically before writing for consistency
            sorted_dirs = sorted(list(penalty_dirs))
            for dir_path in sorted_dirs:
                f_out.write(dir_path + '\n')
        print(f"Successfully wrote directory list to: {output_txt_file}")
    except IOError as e:
        print(f"Error: Could not write to output file {output_txt_file}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred writing the output file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find directories containing potential penalty situations in 'Labels-v2.json' files.")
    parser.add_argument('--data_dir', type=str, required=True,
                        help='The root directory containing game subdirectories.')
    parser.add_argument('--output_file', type=str, required=True,
                        help='The path for the output text file listing the directories.')
    parser.add_argument('--labels_dir', type=str, default='/scratch/users/jmparirwa/penalty_labels',
                        help='The directory to copy the Labels-v2.json files to.')
    
    args = parser.parse_args()
    print(f"Starting search in: {args.data_dir}")
    find_directories_with_penalty(args.data_dir, args.output_file, args.labels_dir)
    print("Search complete.")