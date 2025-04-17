#!/bin/bash
#
#SBATCH --job-name=soccer_download
#SBATCH --output=/home/jmparirwa/master-thesis/download_log_%j.out
#SBATCH --error=/home/jmparirwa/master-thesis/download_error_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=72:00:00   # 72 hours should be enough for a 300GB download
#
# Add any partitions as needed based on your cluster setup
# #SBATCH --partition=batch

# Define paths
HOME_DIR="/home/jmparirwa/master-thesis"
SCRATCH_DIR="/scratch/users/jmparirwa"
DATA_DIR="${SCRATCH_DIR}/data_of_interest"
VENV_DIR="${HOME_DIR}/myenv"  # Path to your virtual environment

# Create data directory if it doesn't exist
mkdir -p ${DATA_DIR}

# Go to the script directory
cd ${HOME_DIR}

# Activate the virtual environment
if [ -d "${VENV_DIR}" ]; then
    echo "Activating virtual environment at ${VENV_DIR}"
    source /home/jmparirwa/master-thesis/myenv/bin/activate
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

# Create a modified version of the download script
cat > ${HOME_DIR}/modified_download.py << EOF
import os
from SoccerNet.Downloader import SoccerNetDownloader

# Use absolute path to scratch filesystem instead of relative path
SCRATCH_DIR = "${SCRATCH_DIR}"
DATA_DIR = os.path.join(SCRATCH_DIR, "data_of_interest")

# Make sure the directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Print the download location for verification
print(f"Downloading data to: {DATA_DIR}")

# Initialize downloader with absolute path
mySoccerNetDownloader = SoccerNetDownloader(LocalDirectory=DATA_DIR)
mySoccerNetDownloader.downloadGames(files=["Labels-v2.json"], split=["train","valid","test"])

# To load videos
mySoccerNetDownloader.password = "s0cc3rn3t"
mySoccerNetDownloader.downloadGames(files=["1_224p.mkv", "2_224p.mkv"], split=["train","valid","test","challenge"])
# mySoccerNetDownloader.downloadGames(files=["1_720p.mkv", "2_720p.mkv", "video.ini"], split=["train","valid","test","challenge"])
EOF

# Run the download script
echo "Starting download at $(date)"
echo "Data will be downloaded to: ${DATA_DIR}"
python ${HOME_DIR}/modified_download.py

# Check the exit code
if [ $? -eq 0 ]; then
    echo "Download completed successfully at $(date)"
else
    echo "Download failed with exit code $? at $(date)"
fi

# Deactivate the virtual environment
deactivate

echo "Job completed at $(date)"
