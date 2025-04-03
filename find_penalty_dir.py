import json
import os
import argparse
import glob

def find_directories_with_penalty(data_dir, output_txt_file):
    """
    Searches for 'Labels-v2.json' files within subdirectories of data_dir,
    checks for a 'Penalty' label within the annotations, and writes the
    paths of directories containing such labels to a text file.
    Args:
        data_dir (str): The root directory containing game subdirectories.
        output_txt_file (str): The path to the output text file to create.
    """
    penalty_dirs = set()  # Use a set to automatically handle duplicates
    
    # Use glob to find all Labels-v2.json files efficiently
    # This assumes game directories are one level below data_dir, adjust if needed
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
        try:
            with open(json_file_path, 'r') as f:
                data = json.load(f)
            annotations = data.get('annotations', [])
            if not annotations:
                # print(f"No annotations found in {json_file_path}")
                continue
            
            found_penalty = False
            for event in annotations:
                if event.get('label') == "Penalty":
                    penalty_dirs.add(game_dir)
                    found_penalty = True
                    # print(f"Found 'Penalty' label in: {game_dir}")
                    break  # No need to check further annotations in this file
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON in file: {json_file_path}")
        except FileNotFoundError:
            # Should not happen with glob/os.walk results, but good practice
            print(f"Warning: File not found (should not happen): {json_file_path}")
        except Exception as e:
            print(f"Warning: An unexpected error occurred processing {json_file_path}: {e}")
    
    # Write the found directories to the output file
    print(f"\nFound {len(penalty_dirs)} directories containing the 'Penalty' label.")
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
    parser = argparse.ArgumentParser(description="Find directories containing 'Labels-v2.json' files with a 'Penalty' label.")
    parser.add_argument('--data_dir', type=str, required=True,
                        help='The root directory containing game subdirectories.')
    parser.add_argument('--output_file', type=str, required=True,
                        help='The path for the output text file listing the directories.')
    
    args = parser.parse_args()
    print(f"Starting search in: {args.data_dir}")
    find_directories_with_penalty(args.data_dir, args.output_file)
    print("Search complete.")