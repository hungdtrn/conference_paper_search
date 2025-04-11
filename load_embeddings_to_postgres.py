import pickle
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def create_tables(conn):
    """Create the papers and workshops tables in PostgreSQL."""
    with conn.cursor() as cur:
        # Create papers table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                paper_id SERIAL PRIMARY KEY,
                title TEXT UNIQUE NOT NULL,
                abstract TEXT,
                authors TEXT[],
                url TEXT,
                pdf_url TEXT,
                title_embedding vector(768),
                abstract_embedding vector(768)
            )
        """)
        
        # Create workshops table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workshops (
                workshop_id SERIAL PRIMARY KEY,
                topic TEXT NOT NULL,
                abstract TEXT,
                url TEXT,
                abstract_embedding vector(768)
            )
        """)
        conn.commit()

def convert_embedding(embedding):
    """Convert ContentEmbedding to list of floats."""
    if embedding is None:
        return None
    return embedding[0].values



def load_embeddings_to_postgres(papers_embeddings_file: str, workshops_embeddings_file: str):
    """Load embeddings from pickle files and store in PostgreSQL."""
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        f"postgresql://neondb_owner:{os.getenv('NEON_DB_PASSWORD')}@ep-purple-tooth-a7v1kx4v-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
    )
    
    try:
        # Create tables
        create_tables(conn)
        
        # Load and process papers embeddings
        with open(papers_embeddings_file, 'rb') as f:
            papers_data = pickle.load(f)
            
        with conn.cursor() as cur:
            # Prepare papers data for insertion
            papers_insert_data = []
            for title, paper in papers_data['papers'].items():
                papers_insert_data.append((
                    title,
                    paper.get('abstract', ''),
                    paper.get('authors', []),
                    paper.get('url', ''),
                    paper.get('pdf_url', ''),
                    convert_embedding(papers_data['titles'].get(title)),
                    convert_embedding(papers_data['abstracts'].get(title))
                ))
            # try:
            #     execute_values(
            #         cur,
            #         """
            #         INSERT INTO papers (title, abstract, authors, url, pdf_url, title_embedding, abstract_embedding)
            #         VALUES %s
            #         """,
            #         papers_insert_data
            #     )
            # except Exception as e:
            #     print(f"Error inserting papers: {e}")
            
            # Load and process workshops embeddings
            with open(workshops_embeddings_file, 'rb') as f:
                workshops_data = pickle.load(f)
                
            # Prepare workshops data for insertion
            workshops_insert_data = []
            for workshop_title, workshop_info in workshops_data.items():
                workshops_insert_data.append((
                    workshop_info['topic'],
                    workshop_info['data'].get('abstract', ''),
                    workshop_info['data'].get('url', ''),
                    convert_embedding(workshop_info['embedding'])
                ))

            try:
                execute_values(
                    cur,
                    """
                    INSERT INTO workshops (topic, abstract, url, abstract_embedding)
                    VALUES %s
                    """,
                    workshops_insert_data
                )
            except Exception as e:
                print(f"Error inserting workshops: {e}")
            
            conn.commit()
            
            # Print statistics
            cur.execute("SELECT COUNT(*) FROM papers")
            total_papers = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM papers WHERE title_embedding IS NOT NULL")
            papers_with_title_emb = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM papers WHERE abstract_embedding IS NOT NULL")
            papers_with_abstract_emb = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM workshops")
            total_workshops = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM workshops WHERE abstract_embedding IS NOT NULL")
            workshops_with_abstract_emb = cur.fetchone()[0]
            
            print(f"Successfully loaded {total_papers} papers")
            print(f"Papers with title embeddings: {papers_with_title_emb}")
            print(f"Papers with abstract embeddings: {papers_with_abstract_emb}")
            print(f"\nSuccessfully loaded {total_workshops} workshops")
            print(f"Workshops with abstract embeddings: {workshops_with_abstract_emb}")
            
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    papers_embeddings_file = "cvpr2025_papers_embeddings.pkl"
    workshops_embeddings_file = "cvpr2025_workshops_embeddings.pkl"
    load_embeddings_to_postgres(papers_embeddings_file, workshops_embeddings_file) 