import os
from SoccerNet.Downloader import SoccerNetDownloader

# Use absolute path to scratch filesystem instead of relative path
SCRATCH_DIR = "/scratch/users/jmparirwa"
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
