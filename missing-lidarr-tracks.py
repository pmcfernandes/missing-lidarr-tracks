from __future__ import unicode_literals
from yt_dlp import YoutubeDL, postprocessor
from yt_dlp.utils import DownloadError
from youtubesearchpython import VideosSearch
from datetime import datetime
from difflib import SequenceMatcher
import os
import shutil
import sqlite3
import eyed3
import unidecode
import json

class FilenameCollectorPP(postprocessor.PostProcessor):
    def __init__(self, downloader=None):
        super().__init__(downloader)
        self.filenames = []

    def run(self, info):
        self.filenames.append(info["filepath"])
        return [], info


class loggerOutputs:
    def error(msg):
        return

    def warning(msg):
        return

    def debug(msg):
        return


class Track:
    def __init__(self, trackId, albumId, title, trackNumber, artist, album, releaseYear, trackCount):
        self.TrackId = trackId
        self.AlbumId = albumId
        self.Title = title
        self.TrackNumber = 0 if not str(trackNumber).isnumeric() else trackNumber
        self.Artist = artist
        self.ReleaseYear = releaseYear
        self.Album = album
        self.TrackCount = trackCount


class Best:
    Ratio = 0
    Title = ""
    Link = ""

    def __init__(self, ratio, title, link):
        self.Ratio = ratio
        self.Title = title
        self.Link = link


def getDefaultYoutubeDLOptions():
    return {
        "quiet": True,
        "logger": loggerOutputs,
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320',
        }]
    }


def createFolder(folderPath):
    if not os.path.exists(folderPath):
        os.makedirs(folderPath)
    pass


def getAlbumPath(track):
    base_path = os.path.join(os.getenv('DOWNLOAD_DIR', '.'), 'albums')
    path = os.path.join(base_path, track.Artist)
    path = os.path.join(path, f"{track.ReleaseYear} - {unidecode.unidecode(track.Album)}")
    return path


def getTrackFullPath(track):
    path = getAlbumPath(track)
    path = os.path.join(path, f"{track.TrackNumber} - {unidecode.unidecode(track.Title)}.mp3")
    return path


def getMissingTracks(conn):
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT ArtistMetadata.name, 
               Tracks.Id, 
               Tracks.Title, 
               AlbumReleases.Title as AlbumTitle, 
               Albums.ReleaseDate, 
               Tracks.TrackNumber, 
               AlbumReleases.TrackCount, 
               Albums.Id as AlbumId
        FROM Tracks 
            INNER JOIN ArtistMetadata ON ArtistMetadata.Id =  Tracks.ArtistMetadataId 
            INNER JOIN Artists ON Artists.ArtistMetadataId = ArtistMetadata.Id
            INNER JOIN AlbumReleases ON AlbumReleases.Id = Tracks.AlbumReleaseId
            INNER JOIN Albums ON Albums.Id = AlbumReleases.AlbumId
        WHERE TrackFileId  = 0 AND Albums.Monitored = 1 AND Artists.Monitored = 1 AND AlbumReleases.Monitored = 1
    """)
    return rows


def updateTrackTable(conn, track, dest):
    fileSize = os.stat(dest).st_size
    dt_now = datetime.now()

    mediainfo = json.dumps({
      "audioFormat": "MPEG Version 1 Audio, Layer 3",
      "audioBitrate": 320,
      "audioChannels": 2,
      "audioBits": 0,
      "audioSampleRate": 44100
    })

    quality = json.dumps({
        "quality": 22,
        "revision": {
            "version": 1,
            "real": 0,
            "isRepack": False
        }
    })

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO TrackFiles (AlbumId, Quality, Size, DateAdded, MediaInfo, Modified, Path)
            VALUES(?, ?, ?, ?, ?, ?, ?)
    """, (track.AlbumId, quality, fileSize, dt_now, mediainfo, dt_now, dest))

    trackFileId = cur.lastrowid

    cur.execute("""
        UPDATE Tracks SET TrackFileId = ? WHERE Id = ?
    """, (trackFileId, track.TrackId))

    try:
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()

    pass


def interactWithTrack(track):
    filePath = getTrackFullPath(track)

    if not os.path.exists(filePath):  # Only download if file not exists local
        searchFor = f"{track.Artist} - {track.Title}"
        results = searchYoutube(searchFor)
        best = Best(0, "", "")

        for video in results:
            video_title = video['title']
            video_url = video['link']

            if SequenceMatcher(None, searchFor, video_title).ratio() > best.Ratio:
                best = Best(SequenceMatcher(None, searchFor, video_title).ratio(), video_title, video_url)

        if best.Ratio < 0.75:
            printYoutubeSearch(best, "Ratio is not minimum required.")
        else:
            downloadedFilename = downloadFromYoutube(best)

            if len(downloadedFilename) == 0:
                printYoutubeSearch(best, "Error downloading track.")
            else:
                printYoutubeSearch(best, f"Downloaded path: {filePath}")

                try:
                    createFolder(getAlbumPath(track))
                    shutil.move(downloadedFilename, filePath)

                    if os.path.exists(filePath):
                        updateMP3Tag(filePath, track)

                    return True

                except IOError as e:
                    if os.path.exists(downloadedFilename):
                        os.remove(downloadedFilename)

    return False


def searchYoutube(searchFor):
    search = VideosSearch(searchFor)

    if search is not None:
        return search.result()['result']
    else:
        print("Error searching youtube. You are connected to internet?")
        exit(1)


def downloadFromYoutube(best):
    with YoutubeDL(getDefaultYoutubeDLOptions()) as yt:
        processor = FilenameCollectorPP()
        yt.add_post_processor(processor)
        try:
            yt.extract_info(best.Link, download=True)
        except DownloadError as e:
            processor.filenames = []

        return "" if len(processor.filenames) == 0 else processor.filenames[0]


def getReleaseAlbumDate(dt):
    if dt is not None:
        return datetime.strptime(str(row[4]), '%Y-%m-%d %H:%M:%SZ')
    else:
        return datetime.strptime('0001-01-01 00:00:00Z', '%Y-%m-%d %H:%M:%SZ')


def updateMP3Tag(fileName, track):
    try:
        audiofile = eyed3.load(fileName)
    except:
        audiofile = None

    if audiofile is not None:
        audiofile.initTag()
        audiofile.tag.clear()
        audiofile.tag.artist = track.Artist
        audiofile.tag.album = track.Album
        audiofile.tag.title = track.Title
        audiofile.tag.track_num = track.TrackNumber
        audiofile.tag.track_total = track.TrackCount
        audiofile.tag.year = track.ReleaseYear
        audiofile.tag.save()
        printTag(f"Updated {fileName} audio tags.")

    pass


def printMissingTrack(track):
    print(f"Album: {track.ReleaseYear} - {track.Album}   Track: {track.TrackNumber}/{track.TrackCount}")
    print("================================================================================")
    print("")
    print(f"  Artist: {track.Artist}")
    print(f"  Album: {track.Album}")
    print(f"  Track: {track.Title}")
    print(f"  Path: {getAlbumPath(track)}")
    print("")


def printYoutubeSearch(best, content):
    ratio = "{:.2f}".format(best.Ratio)

    print("  Youtube search")
    print("  ========================================")
    print("")
    print(f"    Best title: {best.Title}")
    print(f"    Best match: {ratio}")
    print("")
    print(f"    {content}")
    print("")


def printTag(content):
    print("  ID3 Tag update")
    print("  ========================================")
    print("")
    print(f"    {content}")
    print("")


if __name__ == '__main__':
    lidarr_db = os.getenv('LIDARR_DB', '/mnt/cache/appdata/lidarr/lidarr.db')

    if not os.path.exists(lidarr_db):
        print(f'File {lidarr_db} not found.')
        exit(1)

    try:
        conn = sqlite3.connect(lidarr_db)
    except:
        print('Can\'t connect to database lidarr.db')
        exit(1)

    rows = getMissingTracks(conn)
    for row in rows:
        dt = getReleaseAlbumDate(row[4])
        track = Track(
            int(row[1]),  # trackId
            int(row[7]),  # albumId
            str(row[2]),  # trackName
            str(row[5]).rjust(2, '0'),  # trackNumber
            str(row[0]),  # artist
            str(row[3]),  # album
            dt.year,  # releaseYear
            str(row[6])  # trackCount
        )

        printMissingTrack(track)

        if interactWithTrack(track):
            updateTrackTable(conn, track, getTrackFullPath(track))

    conn.close()
