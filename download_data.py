import os
from SoccerNet.Downloader import SoccerNetDownloader


mySoccerNetDownloader = SoccerNetDownloader(LocalDirectory=os.path.join(os.getcwd(), "data_of_interest"))
mySoccerNetDownloader.downloadGames(files=["Labels-v2.json"], split=["train","valid","test"])

# To load videos
# mySoccerNetDownloader.password = input("Password for videos?:\n")
mySoccerNetDownloader.password = "s0cc3rn3t"
mySoccerNetDownloader.downloadGames(files=["1_224p.mkv", "2_224p.mkv"], split=["train","valid","test","challenge"])
# mySoccerNetDownloader.downloadGames(files=["1_720p.mkv", "2_720p.mkv", "video.ini"], split=["train","valid","test","challenge"])