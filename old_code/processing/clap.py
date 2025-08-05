import json

import librosa
import torch
from tqdm import tqdm
from transformers import ClapModel, ClapProcessor

# --- Configuración ---
MODEL_ID = "laion/larger_clap_music_and_speech"
INPUT_FILE = "plex_music_library.json"
OUTPUT_FILE = "music_embeddings.json"
BATCH_SIZE = 16  # Ajustar según la VRAM de la GPU
TARGET_SR = 48000
CHUNK_DURATION_S = 10  # El modelo CLAP está optimizado para 10s

# --- Cargar Modelo y Procesador ---
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Usando dispositivo: {device}")

model = ClapModel.from_pretrained(MODEL_ID).to(device).half()  # .half() para inferencia FP16
processor = ClapProcessor.from_pretrained(MODEL_ID)
model.eval()  # Poner el modelo en modo de evaluación


def get_embedding_for_file(filepath):
    """
    Carga un archivo de audio, lo divide en fragmentos y calcula un embedding promedio.
    """
    try:
        # Cargar y remuestrear el audio
        waveform, sr = librosa.load(filepath, sr=TARGET_SR, mono=True)

        # Dividir en fragmentos de 10 segundos
        chunk_len = CHUNK_DURATION_S * sr
        chunks = [waveform[i:i + chunk_len] for i in range(0, len(waveform), chunk_len)]

        # Asegurarse de que el último chunk no sea demasiado corto
        if len(chunks) > 1 and len(chunks[-1]) < sr:  # Menos de 1 segundo
            chunks.pop(-1)
        if not chunks:
            return None

        # Procesar los fragmentos
        inputs = processor(audios=chunks, sampling_rate=TARGET_SR, return_tensors="pt", padding=True)
        inputs = {k: v.to(device).half() for k, v in inputs.items()}

        with torch.no_grad():
            # Obtener embeddings para todos los fragmentos
            audio_features = model.get_audio_features(**inputs)

            # Promediar los embeddings de los fragmentos y normalizar
            mean_embedding = torch.mean(audio_features, dim=0)
            normalized_embedding = torch.nn.functional.normalize(mean_embedding, p=2, dim=0)

        return normalized_embedding.cpu().numpy().tolist()

    except Exception as e:
        print(f"Error procesando {filepath}: {e}")
        return None


if __name__ == "__main__":
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        library_data = json.load(f)

    all_embeddings_data = []

    for i in tqdm(range(0, len(library_data), BATCH_SIZE), desc="Generando Embeddings"):
        batch_data = library_data

        for track_data in batch_data:
            embedding = get_embedding_for_file(track_data["filepath"])
            if embedding:
                track_data["embedding"] = embedding
                all_embeddings_data.append(track_data)

        # Guardado periódico para evitar pérdida de datos en ejecuciones largas
        if i % (BATCH_SIZE * 10) == 0 and i > 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_embeddings_data, f)

    # Guardado final
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_embeddings_data, f)
    print(
        f"Proceso de embedding completado. {len(all_embeddings_data)} pistas procesadas y guardadas en '{OUTPUT_FILE}'.")