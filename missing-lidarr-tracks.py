from __future__ import unicode_literals
from yt_dlp import YoutubeDL, postprocessor
from yt_dlp.utils import DownloadError
from datetime import datetime
import os
import shutil
import sqlite3
import eyed3
import unidecode


class FilenameCollectorPP(postprocessor.PostProcessor):
    def __init__(self, downloader=None):
        super().__init__(downloader)
        self.filenames = []

    def run(self, info):
        self.filenames.append(info["filepath"])
        return [], info


def createArtistFolder(artist):
    if not os.path.exists(artist):
        os.makedirs(artist)

    return artist


def createAlbumFolder(artist, album):
    folderName = os.path.join(artist, album)
    if not os.path.exists(folderName):
        os.makedirs(folderName)

    return folderName


if __name__ == '__main__':
    lidarr_db = os.getenv('LIDARR_DB', '/mnt/cache/appdata/lidarr/lidarr.db')
    conn = sqlite3.connect(lidarr_db)

    cur = conn.cursor()
    rows = cur.execute("""
    SELECT ArtistMetadata.name, Tracks.Id, Tracks.Title, AlbumReleases.Title as AlbumTitle, Albums.ReleaseDate, Tracks.TrackNumber, AlbumReleases.TrackCount
    FROM Tracks 
        INNER JOIN ArtistMetadata ON ArtistMetadata.Id =  Tracks.ArtistMetadataId 
        INNER JOIN Artists ON Artists.ArtistMetadataId = ArtistMetadata.Id
        INNER JOIN AlbumReleases ON AlbumReleases.Id = Tracks.AlbumReleaseId
        INNER JOIN Albums ON Albums.Id = AlbumReleases.AlbumId
    WHERE TrackFileId  = 0 AND Albums.Monitored = 1 AND Artists.Monitored = 1 AND AlbumReleases.Monitored = 1
    """)

    ydl_opts = {
        "quiet": True,
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320',
        }]
    }

    for row in rows:
        if row[4] is None:
            dt = datetime.strptime('0001-01-01 00:00:00Z', '%Y-%m-%d %H:%M:%SZ')
        else:
            dt = datetime.strptime(str(row[4]), '%Y-%m-%d %H:%M:%SZ')

        artistFolder = createArtistFolder(os.path.join(os.getenv('DOWNLOAD_DIR', '.'), 'albums', str(row[0])))

        albumFolder = f"{dt.year} - {unidecode.unidecode((str(row[3])))}"
        albumFolder = albumFolder.replace("/", "_")
        albumFolder = createAlbumFolder(artistFolder, albumFolder)

        trackNumber = str(row[5]).rjust(2, '0')
        title_decoded = unidecode.unidecode(str(row[2]))
        filePath = f"{albumFolder}/{trackNumber} - {title_decoded}.mp3"

        if not os.path.exists(filePath):  # Only download if file not exists local
            with YoutubeDL(ydl_opts) as yt:
                processor = FilenameCollectorPP()
                yt.add_post_processor(processor)
                try:
                    info = yt.extract_info(f"ytsearch:{str(row[0])} - {str(row[2])}", download=True)
                except DownloadError as e:
                    print(f'Error downloading file {str(row[0])} - {str(row[2])}')
                    continue

                if len(processor.filenames) == 0:
                    print(f'Error downloading file {str(row[0])} - {str(row[2])}')
                    continue

                downloaded_filename = processor.filenames[0]
                print(f"Downloaded file {downloaded_filename}")

                try:
                    shutil.move(downloaded_filename, filePath)
                except:
                    os.remove(downloaded_filename)
                    continue
                finally:
                    try:
                        audiofile = eyed3.load(filePath)
                    except:
                        audiofile = None

                if audiofile is not None:
                    audiofile.initTag()
                    audiofile.tag.clear()

                    audiofile.tag.artist = str(row[0])
                    audiofile.tag.album = str(row[3])
                    audiofile.tag.title = str(row[2])
                    if str(trackNumber).isnumeric():
                        audiofile.tag.track_num = trackNumber
                    audiofile.tag.track_total = str(row[6])
                    if row[4] is not None:
                        audiofile.tag.year = dt.year
                    audiofile.tag.save()

    conn.close()
