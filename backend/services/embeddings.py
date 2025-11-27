import re
from transformers import AutoTokenizer, AutoModel
import numpy as np

tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-mpnet-base-v2')
model = AutoModel.from_pretrained('sentence-transformers/all-mpnet-base-v2')

def clean_lyrics(text: str) -> str:
    # Remove section titles like [Chorus], [Verse 1], etc.
    lyrics = re.sub(r'\[.*?\]', '', text)
    # Remove empty lines or lines that are just whitespace
    lyrics = "\n".join([line.strip() for line in lyrics.split("\n") if line.strip()])
    return lyrics

def split_lyrics(raw_lyrics: str) -> tuple[str, str]:
    song_annotation = ""
    lyrics = raw_lyrics

    if "Read More" in raw_lyrics:
        # Only consider text after Read More
        song_annotation, after_read_more = raw_lyrics.split("Read More", 1)

        # Find the first [Header] like [Intro], [Verse 1], etc.
        match = re.search(r'\[.*?\]', after_read_more)
        if match:
            lyrics = after_read_more[match.start():]
        else:
            lyrics = after_read_more

    return song_annotation.strip(), lyrics.strip()

# Taken from Hugging Face documentation
# Mean Pooling - Take attention mask into account for correct averaging
def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0] # First element of model_output contains all token embeddings
    token_embeddings = np.array(token_embeddings)
    attention_mask = np.array(attention_mask)

    # Expand attention mask from (batch, seq) → (batch, seq, hidden)
    mask_expanded = np.expand_dims(attention_mask, axis=-1)

    # Zero out masked tokens
    masked_embeddings = token_embeddings * mask_expanded

    # Sum over sequence dimension
    sum_embeddings = np.sum(masked_embeddings, axis=1)

    # Count tokens per sample
    token_count = np.clip(np.sum(mask_expanded, axis=1), 1e-9, None)

    return sum_embeddings / token_count

def chunk_lyrics(lyrics: str, max_words: int):
    words = lyrics.split()
    return [' '.join(words[i:i + max_words]) for i in range(0, len(words), max_words)]

def get_song_embedding(lyrics: str):
    if not lyrics.strip():
        return None

    chunks = chunk_lyrics(lyrics, max_words=500) # Set a little below 512 words -> 384 tokens
    embeddings = []

    for chunk in chunks:
        if not chunk.strip():
            continue
        encoded_input = tokenizer(chunk, max_length=384, padding=True, truncation=True, return_tensors='pt')
        model_output = model(**encoded_input)
        chunk_embedding = mean_pooling(model_output, encoded_input['attention_mask'])
        embeddings.append(chunk_embedding[0].cpu().numpy())

    if len(embeddings) == 0:
        return None

    return np.mean(embeddings, axis=0)
