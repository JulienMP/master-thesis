import os
import sys
from SoccerNet.Downloader import SoccerNetDownloader

# Get download directory from environment variable or use default
download_dir = "/scratch/users/jmparirwa/data_tracking"

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
