#!/bin/bash
#SBATCH --job-name=find_penalties
#SBATCH --output=find_penalties_%j.out
#SBATCH --error=find_penalties_%j.err
#SBATCH --time=48:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G

# Define directories
HOME_DIR="/home/jmparirwa/master-thesis"
OUTPUT_DIR="/home/jmparirwa/master-thesis"
# Set the actual path to your game data
DATA_DIR="/scratch/users/jmparirwa/data_of_interest"
VENV_DIR="${HOME_DIR}/myenv"
SCRIPT_PATH="${HOME_DIR}/find_penalty_dirs.py"

# Print job information
echo "Starting penalty directory search job"
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Data directory: $DATA_DIR"
echo "Output directory for list: $OUTPUT_DIR"
echo "Script path: $SCRIPT_PATH"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    echo "Activating virtual environment: $VENV_DIR"
    source "$VENV_DIR/bin/activate"
fi

# Construct the full output file path
OUTPUT_FILE_PATH="${OUTPUT_DIR}/penalty_directories.txt"
echo "Running Python script..."
echo "Command: python $SCRIPT_PATH --data_dir $DATA_DIR --output_file $OUTPUT_FILE_PATH"

# Run the Python script to find directories with penalties
python "$SCRIPT_PATH" \
  --data_dir "$DATA_DIR" \
  --output_file "$OUTPUT_FILE_PATH"

# Deactivate virtual environment if activated
if [ -d "$VENV_DIR" ]; then
    deactivate
fi

# Print job completion
echo "Search completed"
echo "Output list should be in: $OUTPUT_FILE_PATH"
echo "Job completed at: $(date)"
