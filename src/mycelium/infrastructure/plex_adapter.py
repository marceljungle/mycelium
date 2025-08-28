"""Plex integration for accessing music library."""

import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from plexapi.audio import Artist
from plexapi.server import PlexServer
from tqdm import tqdm

from ..domain.models import Track, Playlist, MediaServerType
from ..domain.repositories import PlexRepository


class PlexMusicRepository(PlexRepository):
    """Implementation of PlexRepository for accessing Plex music library."""

    def __init__(
        self,
        plex_url: str = None,
        plex_token: str = None,
        music_library_name: str = "Music"
    ):
        self.plex_url = plex_url
        self.plex_token = plex_token
        self.music_library_name = music_library_name
        self.logger = logging.getLogger(__name__)

    def get_all_tracks(self) -> List[Track]:
        """Get all tracks from the Plex music library."""
        try:
            plex = PlexServer(self.plex_url, self.plex_token, timeout=3600)
            music_lib = plex.library.section(self.music_library_name)
            self.logger.info(f"Connected to Plex. Scanning library '{self.music_library_name}'...")
        except Exception as e:
            raise ConnectionError(f"Error connecting to Plex server: {e}")

        all_tracks = []

        # Hierarchical iteration for better robustness and memory efficiency
        artists = music_lib.all(libtype='artist')
        artists: List[Artist]
        for artist in tqdm(artists, desc="Processing Artists"):
            try:
                for album in artist.albums():
                    for track in album.tracks():
                        for part in track.iterParts():
                            filepath = Path(part.file)
                            if filepath.exists():
                                track_obj = Track(
                                    artist=artist.title,
                                    album=album.title,
                                    title=track.title,
                                    filepath=filepath,
                                    media_server_rating_key=str(track.ratingKey),
                                    media_server_type=MediaServerType.PLEX
                                )
                                all_tracks.append(track_obj)
                            else:
                                self.logger.warning(f"File not found, skipping: {filepath}")
            except Exception as e:
                self.logger.error(f"Error processing artist {artist.title}: {e}. Continuing...", exc_info=True)

        return all_tracks
    
    def get_track_by_id(self, track_id: str) -> Optional[Track]:
        """Get a specific track by Plex rating key."""
        try:
            plex = PlexServer(self.plex_url, self.plex_token)
            track = plex.fetchItem(int(track_id))
            
            # Get the first available part of the track
            for part in track.iterParts():
                filepath = Path(part.file)
                if filepath.exists():
                    return Track(
                        artist=track.grandparentTitle or "Unknown Artist",
                        album=track.parentTitle or "Unknown Album",
                        title=track.title,
                        filepath=filepath,
                        media_server_rating_key=str(track.ratingKey),
                        media_server_type=MediaServerType.PLEX
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting track {track_id}: {e}", exc_info=True)
            return None

    def create_playlist(self, playlist: Playlist) -> Playlist:
        """Create a playlist on the Plex server."""
        try:
            plex = PlexServer(self.plex_url, self.plex_token)
            
            # Get Plex track objects for all tracks in the playlist
            plex_tracks = []
            for track in playlist.tracks:
                try:
                    plex_track = plex.fetchItem(int(track.media_server_rating_key))
                    plex_tracks.append(plex_track)
                except Exception as e:
                    self.logger.warning(f"Could not fetch track {track.media_server_rating_key}: {e}")
                    continue
            
            if not plex_tracks:
                raise ValueError("No valid tracks found for playlist creation")
            
            # Create the playlist on Plex
            created_playlist = plex.createPlaylist(title=playlist.name, items=plex_tracks)
            
            # Return the playlist with server ID and creation time
            return Playlist(
                name=playlist.name,
                tracks=playlist.tracks,
                created_at=datetime.now(),
                server_id=str(created_playlist.ratingKey)
            )
            
        except Exception as e:
            self.logger.error(f"Error creating playlist '{playlist.name}': {e}", exc_info=True)
            raise