import json
import os
import pickle
from typing import List, Dict
from google import genai
from google.genai import types
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Gemini API
client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

def get_embedding(text: str) -> List[float]:
    """Get embedding vector for a given text using Gemini API."""
    try:
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        return result.embeddings
    except Exception as e:
        print(f"Error getting embedding for text: {e}")
        return None

def process_workshops(input_file: str, output_file: str):
    """Process workshops from input JSON file and save embeddings to pickle file."""
    # Read input JSON file
    with open(input_file, 'r') as f:
        workshops_data = json.load(f)
    
    # Create a dictionary to store embeddings
    embeddings = {}
    
    # Process each topic and its workshops
    for topic, workshops in tqdm(workshops_data.items(), desc="Processing topics"):
        for workshop_title, workshop_data in workshops.items():
            # Build the text to embed
            text_to_embed = workshop_title
            
            # Add description if it exists
            if workshop_data.get('abstract'):
                text_to_embed += f"\n{workshop_data['abstract']}"
            
            # Add topics if they exist
            if workshop_data.get('topics'):
                topics_text = "\n".join(workshop_data['topics'])
                text_to_embed += f"\nTopics:\n{topics_text}"
            
            # Get embedding for the concatenated text
            embedding = get_embedding(text_to_embed)
            if embedding:
                # Use workshop title as the key
                embeddings[workshop_title] = {
                    'embedding': embedding,
                    'topic': topic,
                    'url': workshop_data.get('url', '')
                }
    
    # Save results to pickle file
    with open(output_file, 'wb') as f:
        pickle.dump(embeddings, f)

if __name__ == "__main__":
    input_file = "workshops_by_topic.json"
    output_file = "workshops_embeddings.pkl"
    process_workshops(input_file, output_file) 