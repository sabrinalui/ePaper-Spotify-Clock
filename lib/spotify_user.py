import json
import logging
import os
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from datetime import datetime as dt
from typing import Any, Dict, Optional, Tuple

import requests
from requests.exceptions import ReadTimeout
import spotipy
from spotipy.exceptions import SpotifyException

from lib.clock_logging import logger

spotify_logger = logging.getLogger('spotipy.client')

@dataclass_json
@dataclass
class SpotifyTrackMetadata:
    track_name: str
    artist_name: str
    context_type: str  # used to determine context icon
    context_name: str  # context name to be displayed
    track_image_link: str  # link to track image
    album_name: str
    timestamp: dt = field(compare=False)


class SpotifyUser:
    """ 
    Class to handle Spotify User Information needed for Calendar
    """
    def __init__(self, name: str = "CHANGE_ME"):
        self.scope = "user-read-private, user-read-recently-played, user-read-playback-state, user-read-currently-playing"
        self.local_file_path = 'cache/context.json'
        self.redirect_uri = 'http://localhost:8888/callback'
        self.spot_client_id = ''
        self.spot_client_secret = ''
        self.cache = 'cache/.authcache1'
        self.name = name
        self.oauth = None
        self.oauth_token_info = None
        self.sp = None
        self.load_credentials()
        self.update_spotipy_token()

    def load_credentials(self):
        with open('config/keys.json', 'r', encoding='utf-8') as f:
            credentials = json.load(f)
            self.spot_client_id = credentials['spot_client_id'] 
            self.spot_client_secret = credentials['spot_client_secret']

    def update_spotipy_token(self):
        """ 
        Updates Spotify Token from self.oauth if token_info is stale. 
        """
        self.oauth = spotipy.oauth2.SpotifyOAuth(self.spot_client_id, self.spot_client_secret, self.redirect_uri, scope=self.scope, cache_path=self.cache, requests_timeout=10)
        try:
            self.oauth_token_info = self.oauth.get_cached_token()
        except requests.exceptions.ConnectionError:
            logger.error("Failed to update cached_token(): ConnectionError")
            return False

        if self.oauth_token_info:
            self.token = self.oauth_token_info['access_token']
        else:
            auth_url = self.oauth.get_authorize_url()
            print(auth_url)
            response = input("Paste the above link into your browser, then paste the redirect url here: ")
            code = self.oauth.parse_response_code(response)
            if code:
                print("Found Spotify auth code in Request URL! Trying to get valid access token...")
                token_info = self.oauth.get_access_token(code)
                self.token = token_info['access_token']
        self.sp = spotipy.Spotify(auth=self.token)
        logger.info("%s's Spotify access_token granted", self.name)
        return True

    def get_most_recent_spotipy_info(self) -> Optional[SpotifyTrackMetadata]:
        if not self.sp:
            logger.error("%s's SpotipyObject not found", self.name)
            return None
        payload = self.fetch_current_track_from_spotipy()
        if payload and 'item' in payload:
            return self.extract_track_from_current_payload(payload)
        recent_payload = self.fetch_recently_played_track_from_spotipy()
        if recent_payload and 'items' in recent_payload:
            return self.extract_track_from_recent_payload(recent_payload)
        return None

    def fetch_current_track_from_spotipy(self) -> Optional[Dict[str, Any]]:
        """
        Tries to get the currently playing track for the user.
        If it fails due to a SpotifyException or ReadTimeout, it tries to update the Spotify token and retry.
        If it fails due to a ConnectionError, it logs the error and returns None.
        If it fails after 3 attempts, it logs an error message and returns None.

        Returns:
            Optional[Dict[str, Any]]: The currently playing track for the user, or None if it fails to get it.
        """
        for _ in range(3):
            try:
                return self.sp.current_user_playing_track()
            except (SpotifyException, ReadTimeout) as e:
                logger.error(e)
                self.update_spotipy_token()
            except requests.exceptions.ConnectionError as e:
                logger.error(e)
                return None
        logger.error("Failed to get current %s's Spotify Info", self.name)
        return None


    def fetch_recently_played_track_from_spotipy(self) -> Optional[Dict[str, Any]]:
        for _ in range(3):
            try:
                return self.sp.current_user_recently_played(1)
            except (SpotifyException, ReadTimeout) as e:
                logger.error(e)
                if 'The access token expired' in str(e):
                    self.update_spotipy_token()
            except requests.exceptions.ConnectionError as e:
                logger.error(e)
                return None
        logger.error(f"Failed to get current {self.name}'s recently played track")
        return None


    def extract_track_from_current_payload(self, recent: Dict[str, Any]) -> SpotifyTrackMetadata:
        """
        Extracts the currently playing information from the given recent track data.

        Args:
            recent (Dict[str, Any]): The recent track data.

        Returns:
            SpotifyTrackMetadata
        """
        context_type, context_name = self.get_context_from_json(recent)
        track_name, artists = recent['item']['name'], recent['item']['artists']
        artist_name = ', '.join(artist['name'] for artist in artists)
        track_image_link, album_name = self.get_track_image_and_album(recent)
        track = SpotifyTrackMetadata(
            track_name=track_name,
            artist_name=artist_name,
            context_type=context_type,
            context_name=context_name,
            track_image_link=track_image_link,
            album_name=album_name,
            timestamp=dt.now(),
        )
        logger.info(f"Successfully fetched Spotify track: {track}")
        return track


    def extract_track_from_recent_payload(self, recent: Dict[str, Any]) -> SpotifyTrackMetadata:
        """
        Extracts the track information from the given recent track data.

        Args:
            recent (Dict[str, Any]): The recent track data.
            unix_timestamp (int): The timestamp of the track.

        Returns:
            SpotifyTrackMetadata
        """
        tracks = recent["items"]
        track = tracks[0]
        track_name, artists = track['track']['name'], track['track']['artists']
        track_image_link = track['track']['album']['images'][0]['url']
        album_name = track['track']['album']['name']
        artist_name = ', '.join(artist['name'] for artist in artists)
        context_type, context_name = self.get_context_from_json(track)
        track = SpotifyTrackMetadata(
            track_name=track_name,
            artist_name=artist_name,
            context_type=context_type,
            context_name=context_name,
            track_image_link=track_image_link,
            album_name=album_name,
            timestamp=dt.now(),
        )
        logger.info(f"Successfully fetched Spotify track: {track}")
        return track


    def get_track_image_and_album(self, recent: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts the track image URL and album name from the given recent track data.

        Args:
            recent (Dict[str, Any]): The recent track data.

        Returns:
            Tuple[Optional[str], Optional[str]]: 
                track_image_link: link to the track image
                album_name: name of the album, or None if not a single user
        """
        return recent['item']['album']['images'][0]['url'], recent['item']['album']['name']


    def get_context_from_json(self, track_json: Dict[str, Any]) -> Tuple[str, str]:
        """
        Returns Spotify Context info.

        Args:
            track_json (Dict[str, Any]): The track data to be parsed.

        Returns:
            Tuple[str, str]: 
                context_type: Either a playlist, artist, or album.
                context_name: Context name to be displayed.
        """
        context_type, context_name = "", ""
        context_json = track_json.get('context')

        if context_json:
            context_type = context_json['type']
            context_uri = context_json['uri']
        else:
            context_type = "album"
            track_info = track_json.get('track') or track_json.get('item')
            context_uri = track_info['album']['uri']

        context_fetchers = {
            'playlist': self.sp.playlist,
            'album': self.sp.album,
            'artist': self.sp.artist
        }

        fetcher = context_fetchers.get(context_type)

        if fetcher:
            spotify_logger.disabled = True
            try:
                context_name = fetcher(context_uri)['name']
            except SpotifyException:
                if context_type == 'playlist':
                    context_name = "DJ"
        elif context_type == 'collection':
            context_name = "Liked Songs"

        spotify_logger.disabled = False
        return context_type, context_name

    def write_track_to_cache(self, obj: SpotifyTrackMetadata) -> None:
        """
        Updates context.json with spotify user context.
        """
        try:
            logger.info(f"writing track to {self.local_file_path}: {obj}")
            with open(self.local_file_path, 'w+', encoding='utf-8') as j_cxt:
                json.dump(obj.to_dict(), j_cxt, indent=4)
        except (FileNotFoundError, PermissionError) as e:
            logger.error(f"error writing {self.local_file_path}: {e}, contents: {obj.to_dict()}")

    def read_track_from_cache(self) -> Optional[SpotifyTrackMetadata]:
        if os.path.exists(self.local_file_path):
            with open(self.local_file_path, 'r', encoding='utf-8') as j_cxt:
                try:
                    ctx = json.load(j_cxt)
                    obj = SpotifyTrackMetadata.from_dict(ctx)
                    return obj
                except (json.JSONDecodeError, IndexError) as e:
                    logger.error(f"error reading {self.local_file_path}: {e}")
        return None