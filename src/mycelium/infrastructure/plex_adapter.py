"""Plex integration for accessing music library."""

import os
from typing import List, Optional
from pathlib import Path

from plexapi.server import PlexServer
from tqdm import tqdm

from ..domain.models import Track
from ..domain.repositories import PlexRepository


class PlexMusicRepository(PlexRepository):
    """Implementation of PlexRepository for accessing Plex music library."""
    
    def __init__(
        self,
        plex_url: str = None,
        plex_token: str = None,
        music_library_name: str = "Music"
    ):
        self.plex_url = plex_url or os.environ.get("PLEX_URL", "http://localhost:32400")
        self.plex_token = plex_token or os.environ.get("PLEX_TOKEN")
        self.music_library_name = music_library_name
        
        if not self.plex_token:
            raise ValueError("PLEX_TOKEN must be provided either as parameter or environment variable")
    
    def get_all_tracks(self) -> List[Track]:
        """Get all tracks from the Plex music library."""
        try:
            plex = PlexServer(self.plex_url, self.plex_token)
            music_lib = plex.library.section(self.music_library_name)
            print(f"Connected to Plex. Scanning library '{self.music_library_name}'...")
        except Exception as e:
            raise ConnectionError(f"Error connecting to Plex server: {e}")

        all_tracks = []

        # Hierarchical iteration for better robustness and memory efficiency
        artists = music_lib.all()
        for artist in tqdm(artists, desc="Processing Artists"):
            try:
                for album in artist.albums():
                    for track in album.tracks():
                        # track.iterParts() handles multiple versions of a file
                        for part in track.iterParts():
                            filepath = Path(part.file)
                            if filepath.exists():
                                track_obj = Track(
                                    artist=artist.title,
                                    album=album.title,
                                    title=track.title,
                                    filepath=filepath,
                                    plex_rating_key=str(track.ratingKey)
                                )
                                all_tracks.append(track_obj)
                            else:
                                print(f"WARNING: File not found, skipping: {filepath}")
            except Exception as e:
                print(f"Error processing artist {artist.title}: {e}. Continuing...")

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
                        plex_rating_key=str(track.ratingKey)
                    )
            
            return None
            
        except Exception as e:
            print(f"Error getting track {track_id}: {e}")
            return None