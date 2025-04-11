import json
import time
from typing import List, Dict
from cvpr2025_crawler import CVPR2025Crawler

def load_papers(json_file: str) -> List[Dict]:
    """Load papers from JSON file."""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_papers(papers: List[Dict], json_file: str):
    """Save papers to JSON file."""
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

def update_missing_abstracts():
    # Initialize crawler
    crawler = CVPR2025Crawler()
    
    # Load existing papers
    papers = load_papers('cvpr2025_papers.json')
    
    # Find papers with empty abstracts
    papers_to_update = [paper for paper in papers if not paper.get('abstract')]
    print(f"Found {len(papers_to_update)} papers with missing abstracts")
    
    # Try to get abstracts for each paper
    for i, paper in enumerate(papers_to_update, 1):
        title = paper['title']
        print(f"\nProcessing paper {i}/{len(papers_to_update)}: {title}")
        
        # Try arXiv first
        abstract = crawler.search_arxiv(title)
        if not abstract:
            # If arXiv fails, try Semantic Scholar
            abstract = crawler.search_semantic_scholar(title)
        
        if abstract:
            paper['abstract'] = abstract
            print("Successfully found abstract")
        else:
            print("Could not find abstract")
        
        # Save progress after each paper
        save_papers(papers, 'cvpr2025_papers.json')
        print("Progress saved")
        
        # Add a small delay to avoid rate limiting
        time.sleep(1)

if __name__ == "__main__":
    update_missing_abstracts() 