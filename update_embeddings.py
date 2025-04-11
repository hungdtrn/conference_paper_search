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

def update_missing_embeddings(papers_file: str, embeddings_file: str):
    """Update missing embeddings in the saved embeddings file."""
    # Load papers data
    with open(papers_file, 'r') as f:
        papers = json.load(f)
    
    # Load existing embeddings or create new structure
    try:
        with open(embeddings_file, 'rb') as f:
            embeddings = pickle.load(f)
    except (FileNotFoundError, EOFError):
        embeddings = {
            'papers': {},  # Store complete paper data
            'titles': {},  # Store title embeddings
            'abstracts': {}  # Store abstract embeddings
        }
    
    # Initialize counters
    missing_titles = 0
    missing_abstracts = 0
    new_papers = 0
    
    if "papers" not in embeddings:
        embeddings["papers"] = {}
        
    # Check for missing embeddings and update paper data
    for paper in tqdm(papers, desc="Checking missing embeddings"):
        paper_id = paper['title']
        
        # Update paper data if not present or different
        # if paper_id not in embeddings['papers'] or embeddings['papers'][paper_id] != paper:
        #     embeddings['papers'][paper_id] = paper
        #     new_papers += 1
        
        # Check title embedding
        if paper_id not in embeddings['titles'] or embeddings['titles'][paper_id] is None:
            title_embedding = get_embedding(paper['title'])
            if title_embedding:
                embeddings['titles'][paper_id] = title_embedding
                missing_titles += 1
        
        # Check abstract embedding
        if paper_id not in embeddings['abstracts'] or embeddings['abstracts'][paper_id] is None:
            abstract_embedding = get_embedding(paper['abstract'])
            if abstract_embedding:
                embeddings['abstracts'][paper_id] = abstract_embedding
                missing_abstracts += 1

        embeddings['papers'][paper_id] = paper
    
    # Save updated embeddings
    with open(embeddings_file, 'wb') as f:
        pickle.dump(embeddings, f)
    
    print(f"\nUpdated {missing_titles} missing title embeddings")
    print(f"Updated {missing_abstracts} missing abstract embeddings")
    print(f"Added/Updated {new_papers} paper records")

if __name__ == "__main__":
    papers_file = "cvpr2025_papers.json"
    embeddings_file = "cvpr2025_papers_embeddings.pkl"
    update_missing_embeddings(papers_file, embeddings_file) 