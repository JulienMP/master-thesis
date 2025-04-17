#!/bin/bash
#SBATCH --job-name=extract_background
#SBATCH --output=extract_background_%j.out
#SBATCH --error=extract_background_%j.err
#SBATCH --time=24:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G

# Define directories
HOME_DIR="/home/jmparirwa/master-thesis"
SCRATCH_DIR="/scratch/users/jmparirwa"
DATA_DIR="${SCRATCH_DIR}/data_of_interest"
OUTPUT_DIR="${SCRATCH_DIR}/background"
VENV_DIR="${HOME_DIR}/myenv"  # Path to your virtual environment
SCRIPT_PATH="${HOME_DIR}/extract_background.py"

# Set number of clips per game and limit
CLIPS_PER_GAME=3  # Extract 3 clips per game
LIMIT="${1:-0}"  # Default to 10 games, or use command line argument if provided

# Print job information
echo "Starting background clip extraction job"
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Data directory: $DATA_DIR"
echo "Output directory: $OUTPUT_DIR"
echo "Script path: $SCRIPT_PATH"
echo "Clips per game: $CLIPS_PER_GAME"
if [ -z "$1" ]; then
    echo "Processing 10 games (default)"
else
    echo "Game limit: $LIMIT"
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    echo "Activating virtual environment: $VENV_DIR"
    source "$VENV_DIR/bin/activate"
fi

# Run the Python script to extract background clips
python "$SCRIPT_PATH" \
  --data_dir "$DATA_DIR" \
  --output_dir "$OUTPUT_DIR" \
  --clips_per_game "$CLIPS_PER_GAME" \
  --limit "$LIMIT"

# Deactivate virtual environment if activated
if [ -d "$VENV_DIR" ]; then
    deactivate
fi

# Print job completion
echo "Background clip extraction completed"
echo "Job completed at: $(date)"
