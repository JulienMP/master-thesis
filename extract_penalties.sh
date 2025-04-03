#!/bin/bash
#SBATCH --job-name=extract_penalties
#SBATCH --output=extract_penalties_%j.out
#SBATCH --error=extract_penalties_%j.err
#SBATCH --time=48:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G

# Define directories
HOME_DIR="/home/jmparirwa/master-thesis"
SCRATCH_DIR="/scratch/users/jmparirwa"
DATA_DIR="${SCRATCH_DIR}/data_of_interest"
OUTPUT_DIR="${SCRATCH_DIR}/penalties"
VENV_DIR="${HOME_DIR}/myenv"  # Path to your virtual environment
SCRIPT_PATH="${HOME_DIR}/extract_penalties.py"

# Set trigger window (max seconds before a Penalty to look for a trigger event)
TRIGGER_WINDOW=5

# Print job information
echo "Starting penalty clip extraction job"
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Data directory: $DATA_DIR"
echo "Output directory: $OUTPUT_DIR"
echo "Script path: $SCRIPT_PATH"
echo "Penalty trigger lookback window: $TRIGGER_WINDOW seconds"
echo "Processing ALL games (no limit)"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    echo "Activating virtual environment: $VENV_DIR"
    source "$VENV_DIR/bin/activate"
fi

# Run the Python script to extract penalty clips
python "$SCRIPT_PATH" \
  --data_dir "$DATA_DIR" \
  --output_dir "$OUTPUT_DIR" \
  --window "$TRIGGER_WINDOW"

# Deactivate virtual environment if activated
if [ -d "$VENV_DIR" ]; then
    deactivate
fi

# Print job completion
echo "Penalty clip extraction completed"
echo "Job completed at: $(date)"