import os
from plexapi.server import PlexServer
from tqdm import tqdm
import json

# --- Configuración ---
PLEX_URL = os.environ.get("PLEX_URL", "http://localhost:32400")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "TU_PLEX_TOKEN")
MUSIC_LIBRARY_NAME = "Music"
OUTPUT_FILE = "plex_music_library.json"


def get_music_library_paths():
    """
    Escanea la biblioteca de música de Plex de forma jerárquica y robusta
    para extraer las rutas de archivo y metadatos de todas las pistas.
    """
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        music_lib = plex.library.section(MUSIC_LIBRARY_NAME)
        print(f"Conectado a Plex. Escaneando la biblioteca '{MUSIC_LIBRARY_NAME}'...")
    except Exception as e:
        print(f"Error al conectar con el servidor de Plex: {e}")
        return

    all_tracks_data = []

    # Iteración jerárquica para mayor robustez y eficiencia de memoria
    artists = music_lib.all()
    for artist in tqdm(artists, desc="Procesando Artistas"):
        try:
            for album in artist.albums():
                for track in album.tracks():
                    # track.iterParts() maneja múltiples versiones de un archivo
                    for part in track.iterParts():
                        filepath = part.file
                        if os.path.exists(filepath):
                            track_data = {
                                "artist": artist.title,
                                "album": album.title,
                                "track_title": track.title,
                                "filepath": filepath,
                                "plex_rating_key": str(track.ratingKey)
                            }
                            all_tracks_data.append(track_data)
                        else:
                            print(f"ADVERTENCIA: Archivo no encontrado, omitiendo: {filepath}")
        except Exception as e:
            print(f"Error procesando al artista {artist.title}: {e}. Continuando...")

    return all_tracks_data


if __name__ == "__main__":
    track_list = get_music_library_paths()
    if track_list:
        print(f"Proceso completado. Se encontraron {len(track_list)} archivos de pistas.")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(track_list, f, indent=4, ensure_ascii=False)
        print(f"Los datos de la biblioteca se han guardado en '{OUTPUT_FILE}'.")