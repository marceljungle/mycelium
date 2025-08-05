import chromadb
import json
from tqdm import tqdm

from processing.clap import get_embedding_for_file

# --- Configuración ---
DB_PATH = "./music_vector_db"
COLLECTION_NAME = "my_music_library"
INPUT_FILE = "music_embeddings.json"
BATCH_SIZE = 1000

# --- Inicializar Cliente y Colección de ChromaDB ---
client = chromadb.PersistentClient(path=DB_PATH)

# Usar 'get_or_create_collection' para idempotencia
# Especificar la métrica de distancia 'cosine' es crucial para embeddings normalizados
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"}
)
print(f"Colección '{COLLECTION_NAME}' lista. Total de elementos actuales: {collection.count()}")

# --- Cargar datos y poblar la base de datos ---
with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    embedding_data = json.load(f)

print(f"Cargados {len(embedding_data)} embeddings para indexar.")

# Preparar datos para la inserción por lotes
ids =[]
embeddings = []
metadatas = []

for item in embedding_data:
    # El ID debe ser único. Usar la ruta del archivo sanitizada o el ratingKey es una buena estrategia.
    ids.append(item["plex_rating_key"])
    embeddings.append(item["embedding"])
    metadatas.append({
        "filepath": item["filepath"],
        "artist": item["artist"],
        "album": item["album"],
        "title": item["track_title"]
    })

# Insertar en ChromaDB por lotes para máxima eficiencia
for i in tqdm(range(0, len(ids), BATCH_SIZE), desc="Indexando en ChromaDB"):
    id_batch = ids
    embedding_batch = embeddings
    metadata_batch = metadatas

    collection.add(
        ids=id_batch,
        embeddings=embedding_batch,
        metadatas=metadata_batch
    )

print("¡Indexación completada!")
print(f"Total de elementos en la colección '{COLLECTION_NAME}': {collection.count()}")


def find_similar_by_audio(filepath, n_results=10):
    """
    Encuentra canciones similares a un archivo de audio dado.
    """
    print(f"\nBuscando canciones similares a: {os.path.basename(filepath)}")

    # Generar el embedding para la canción de consulta
    query_embedding = get_embedding_for_file(filepath)

    if query_embedding is None:
        print("No se pudo generar el embedding para la consulta.")
        return

    # Consultar a ChromaDB
    # Pedimos n_results + 1 para poder descartar el resultado que es la propia canción
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results + 1
    )

    print("\nResultados de la recomendación:")
    for i in range(len(results['ids'])):
        metadata = results['metadatas'][i]
        distance = results['distances'][i]

        # Omitir si es la misma canción
        if metadata['filepath'] == filepath:
            continue

        print(f"  - Distancia: {distance:.4f} | {metadata['artist']} - {metadata['title']}")


def find_similar_by_text(query_text, n_results=10):
    """
    Encuentra canciones que coincidan con una descripción de texto.
    """
    print(f"\nBuscando canciones para la consulta: '{query_text}'")

    # Generar el embedding para la consulta de texto
    text_inputs = processor(text=[query_text], return_tensors="pt", padding=True)
    text_inputs = {k: v.to(device) for k, v in text_inputs.items()}

    with torch.no_grad():
        text_features = model.get_text_features(**text_inputs)
        text_embedding = torch.nn.functional.normalize(text_features, p=2, dim=-1)

    query_embedding = text_embedding.cpu().numpy().tolist()

    # Consultar a ChromaDB
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )

    print("\nResultados de la búsqueda semántica:")
    for i in range(len(results['ids'])):
        metadata = results['metadatas'][i]
        distance = results['distances'][i]
        print(f"  - Distancia: {distance:.4f} | {metadata['artist']} - {metadata['title']}")


# --- Ejemplo de uso del motor de consulta ---
if __name__ == "__main__":
    # Asegúrate de que la colección está cargada
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)

    # Cargar el modelo y procesador para las consultas
    model = ClapModel.from_pretrained(MODEL_ID).to(device).half()
    processor = ClapProcessor.from_pretrained(MODEL_ID)
    model.eval()

    # Ejemplo de consulta por audio (reemplaza con una ruta de tu biblioteca)
    # first_track_path = embedding_data['filepath']
    # find_similar_by_audio(first_track_path)

    # Ejemplos de consulta por texto
    find_similar_by_text("upbeat 80s synthpop with female vocals")
    find_similar_by_text("acoustic folk song with a melancholic mood")
    find_similar_by_text("instrumental jazz trio, piano, bass, drums")