#!/bin/bash
#
#SBATCH --job-name=soccer_tracking_download
#SBATCH --output=/home/jmparirwa/master-thesis/tracking_download_log_%j.out
#SBATCH --error=/home/jmparirwa/master-thesis/tracking_download_error_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=48:00:00   # 48 hours for tracking data download
#
# Add any partitions as needed based on your cluster setup
# #SBATCH --partition=batch

# Define paths
HOME_DIR="/home/jmparirwa/master-thesis"
SCRATCH_DIR="/scratch/users/jmparirwa"
DATA_DIR="${SCRATCH_DIR}/data_tracking"
VENV_DIR="${HOME_DIR}/myenv"  # Path to your virtual environment

# Create data directory if it doesn't exist
mkdir -p ${DATA_DIR}

# Go to the script directory
cd ${HOME_DIR}

# Activate the virtual environment
if [ -d "${VENV_DIR}" ]; then
    echo "Activating virtual environment at ${VENV_DIR}"
    source ${VENV_DIR}/bin/activate
    # Verify activation
    which python
    python --version
    pip list | grep -E 'torch|soccernet'
else
    echo "ERROR: Virtual environment not found at ${VENV_DIR}"
    echo "Please create the virtual environment before submitting this job"
    exit 1
fi

# Set environment variable to specify where to download the data
export PYTHONPATH="${HOME_DIR}:${PYTHONPATH}"

# Create the Python download script
cat > ${HOME_DIR}/download_tracking.py << EOF
import os
import sys
from SoccerNet.Downloader import SoccerNetDownloader

# Get download directory from environment variable or use default
download_dir = "${DATA_DIR}"

print(f"Downloading tracking data to: {download_dir}")
print(f"Python version: {sys.version}")

try:
    # Initialize downloader with specified path
    mySoccerNetDownloader = SoccerNetDownloader(LocalDirectory=download_dir)
    
    # Download tracking data
    print("Downloading tracking task data...")
    mySoccerNetDownloader.downloadDataTask(task="tracking", split=["train","test","challenge"])
    
    print("Downloading tracking-2023 task data...")
    mySoccerNetDownloader.downloadDataTask(task="tracking-2023", split=["train", "test", "challenge"])
    
    print("Download completed successfully!")

except Exception as e:
    print(f"Error during download: {e}")
    sys.exit(1)
EOF

# Run the download script
echo "Starting tracking data download at $(date)"
echo "Data will be downloaded to: ${DATA_DIR}"
python ${HOME_DIR}/download_tracking.py

# Check the exit code
if [ $? -eq 0 ]; then
    echo "Tracking data download completed successfully at $(date)"
else
    echo "Tracking data download failed with exit code $? at $(date)"
fi

# Deactivate the virtual environment
deactivate

echo "Job completed at $(date)"
