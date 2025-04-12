from flask import Flask, render_template, request, jsonify
import json
import os
import psycopg2
from dotenv import load_dotenv
from google import genai
from google.genai import types
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from typing import List, Set


nltk.data.path.append("/tmp")

# Download required NLTK data
nltk.download('punkt', download_dir='/tmp')
nltk.download('stopwords', download_dir='/tmp')
nltk.download('wordnet', download_dir='/tmp')
nltk.download('punkt_tab', download_dir='/tmp')

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Gemini API
client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

# Initialize NLTK components
stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

def generate_synonyms(query: str) -> List[str]:
    """Generate synonyms for the query using Gemini API."""
    prompt = f"""Given the research query: "{query}"
Generate 9 different variations of this query that a researcher might use to search for the same topic.
Focus on academic and technical variations. The variations should be different from the original query.
Avoid using generic words like "research", "study", "explore", "investigate".
Return only the variations, one per line, without any additional text or numbering."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite-001",
            contents=prompt
        )
        variations = response.text.strip().split('\n')
        # Add original query to the list
        variations = [query] + variations
        return variations
    except Exception as e:
        print(f"Error generating synonyms: {e}")
        return [query]

def extract_keywords(query: str) -> List[str]:
    """Extract keywords from the query using NLTK."""
    # Tokenize the query
    tokens = word_tokenize(query.lower())
    
    # Remove stopwords and lemmatize
    keywords = []
    for token in tokens:
        # Allow hyphenated words and words with apostrophes
        if (token.replace('-', '').replace("'", "").isalnum() and 
            token not in stop_words and 
            len(token) > 2):
            # Lemmatize the word to get its base form
            lemma = lemmatizer.lemmatize(token)
            keywords.append(lemma)
    
    return list(set(keywords))  # Remove duplicates

def get_embedding(text: str) -> List[float]:
    """Get embedding vector for a given text using Gemini API."""
    try:
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"Error getting embedding for text: {e}")
        return None

def get_embeddings(text: List[str]) -> List[List[float]]:
    """Get embedding vectors for a list of texts using Gemini API."""
    try:
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        return [result.embeddings[i].values for i in range(len(result.embeddings))]
    except Exception as e:
        print(f"Error getting embeddings for texts: {e}")
        return []

def get_db_connection():
    """Create a connection to the PostgreSQL database."""
    return psycopg2.connect(
        f"postgresql://neondb_owner:{os.getenv('NEON_DB_PASSWORD')}@ep-purple-tooth-a7v1kx4v-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query', '')
    search_papers = request.form.get('search_papers', 'true').lower() == 'true'
    search_workshops = request.form.get('search_workshops', 'true').lower() == 'true'
    
    if not query:
        return jsonify([])
    
    # Generate query variations
    query_variations = generate_synonyms(query)
    print(f"Generated query variations: {query_variations}")
    
    # Get embeddings for all variations
    query_embeddings = get_embeddings(query_variations)
    print("Len of query embeddings: ", len(query_embeddings))
    if not query_embeddings:
        return jsonify([])
    
    # Connect to database and perform semantic search
    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return jsonify([])
    
    try:
        all_results = []
        seen_titles = set()
        
        # Search for each query variation
        for query_id, query_embedding in enumerate(query_embeddings):
            # Extract keywords from all query variations
            all_keywords = extract_keywords(query_variations[query_id])
            print("All keywords: ", all_keywords, "for query: ", query_variations[query_id])
            
            with conn.cursor() as cur:
                # Search workshops first if enabled
                if search_workshops:
                    cur.execute("""
                        SELECT topic, abstract, url,
                               (abstract_embedding <=> %s::vector) as distance
                        FROM workshops
                        WHERE abstract_embedding IS NOT NULL
                        ORDER BY distance
                        LIMIT 20
                    """, (query_embedding,))
                    
                    for row in cur.fetchall():
                        title = row[0]
                        if title in seen_titles:
                            continue
                            
                        abstract = row[1].lower()
                        
                        # Check keyword presence ratio
                        combined_text = title.lower() + " " + abstract
                        combined_text = combined_text.replace("'", "").replace("-", "")
                        keyword_exists = [keyword in combined_text for keyword in all_keywords]
                        exists_ratio = sum(keyword_exists) / len(all_keywords) if all_keywords else 1.0
                        if exists_ratio < 0.6:
                            continue
                        seen_titles.add(title)
                        all_results.append({
                            'title': title,
                            'abstract': row[1],
                            'authors': None,
                            'link': row[2],
                            'score': (1 - row[3]),
                            'type': 'workshop'
                        })

                print("All results: ", all_results)

                # Search papers if enabled
                if search_papers:
                    cur.execute("""
                        SELECT title, abstract, authors, url, pdf_url,
                               (0.1 * (title_embedding <=> %s::vector) + 0.9 * (abstract_embedding <=> %s::vector)) as distance
                        FROM papers
                        WHERE title_embedding IS NOT NULL AND abstract_embedding IS NOT NULL
                        ORDER BY distance
                        LIMIT 50
                    """, (query_embedding, query_embedding))
                    
                    for row in cur.fetchall():
                        title = row[0]
                        if title in seen_titles:
                            continue
                            
                        abstract = row[1].lower()
                        
                        # Check keyword presence ratio
                        combined_text = title.lower() + " " + abstract
                        combined_text = combined_text.replace("'", "").replace("-", "")
                        keyword_exists = [keyword in combined_text for keyword in all_keywords]
                        exists_ratio = sum(keyword_exists) / len(all_keywords) if all_keywords else 1.0
                        if exists_ratio < 0.5:
                            continue
                        seen_titles.add(title)
                        all_results.append({
                            'title': title,
                            'abstract': row[1],
                            'authors': row[2],
                            'link': row[3] or row[4],  # Use url or pdf_url as link
                            'score': (1 - row[5]),   # Convert distance to similarity score
                            'type': 'paper'
                        })
                        
                print("All results: ", all_results)

        # Sort all results by type (workshops first) and then by score
        all_results.sort(key=lambda x: (x['type'] == 'workshop', -x['score']))
        all_results.sort(key=lambda x: (x['type'] != 'workshop', -x['score']))

        return jsonify(all_results[:20])
            
    except Exception as e:
        print(f"Error searching database: {e}")
        raise e
        return jsonify([])
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)