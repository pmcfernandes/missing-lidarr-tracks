# missing-lidarr-tracks.py
Sometimes is not possible to get some tracks or albums at all from Torrents, to get these tracks you can use Youtube (as your friend) to get this for missing files.

This program help you get these files from youtube. It's made for **Unraid** but can be used in Linux or Windows.

### Installation

 1. Install **NerdTools** plugin 
 2. From **NerdTools** install **Python**
 3. In cache disk push this repository
 4. Enter in folder of repo and next install Python dependencies using command **pip install -r requirements.txt**
 

#### Usage

	export LIDARR_DB=/mnt/cache/appdata/lidarr/lidarr.db
	export DOWNLOAD_DIR=/mnt/user/downloads/missing_tracks/
	missing-lidarr-tracks.py

You can use the "User Scripts" plugin to create a cronjob to run periodically this task.