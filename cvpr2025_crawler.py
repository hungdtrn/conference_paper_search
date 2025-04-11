import requests
from bs4 import BeautifulSoup
import json
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote
import re
from typing import List, Tuple
from tqdm import tqdm

class CVPR2025Crawler:
    def __init__(self, base_url: str = "https://cvpr.thecvf.com"):
        self.base_url = base_url
        self.session = requests.Session()
        # Add headers to mimic browser behavior
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # Rate limiting for arXiv API
        self.last_request_time = 0
        self.min_request_interval = 3  # seconds between requests

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content with error handling and retries."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"Failed to fetch {url}: {str(e)}")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
        return None

    def search_arxiv(self, title: str) -> Optional[str]:
        """Search arXiv for paper abstract using title."""
        try:
            # Rate limiting
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.min_request_interval:
                time.sleep(self.min_request_interval - time_since_last_request)
            
            # Clean the title for search
            search_title = re.sub(r'[^\w\s]', '', title)
            search_title = ' '.join(search_title.split())
            
            # Search arXiv
            search_url = f"http://export.arxiv.org/api/query?search_query=ti:{quote(search_title)}&max_results=1"
            response = self.session.get(search_url)
            response.raise_for_status()
            
            # Update last request time
            self.last_request_time = time.time()
            
            # Parse XML response
            soup = BeautifulSoup(response.text, 'xml')
            entry = soup.find('entry')
            if entry:
                summary = entry.find('summary')
                if summary:
                    return summary.text.strip()
        except Exception as e:
            print(f"Error searching arXiv for '{title}': {str(e)}")
        return None

    def search_semantic_scholar(self, title: str) -> Optional[str]:
        """Search Semantic Scholar for paper abstract using title."""
        try:
            # Clean the title for search
            search_title = re.sub(r'[^\w\s]', '', title)
            search_title = ' '.join(search_title.split())
            
            # Search Semantic Scholar
            search_url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(search_title)}&limit=1"
            response = self.session.get(search_url)
            response.raise_for_status()
            
            data = response.json()
            if data.get('total') > 0:
                paper_id = data['papers'][0]['paperId']
                # Get paper details
                paper_url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields=abstract"
                paper_response = self.session.get(paper_url)
                paper_response.raise_for_status()
                paper_data = paper_response.json()
                if 'abstract' in paper_data:
                    return paper_data['abstract']
        except Exception as e:
            print(f"Error searching Semantic Scholar for '{title}': {str(e)}")
        return None

    def get_abstract(self, title: str) -> str:
        """Get abstract from arXiv."""
        abstract = self.search_arxiv(title)
        return abstract if abstract else ""

    def parse_paper(self, row) -> Dict:
        """Parse a single paper row from the table."""
        paper_data = {"year": 2025}
        
        # Extract title and link if available
        title_cell = row.find('td')
        if title_cell:
            title_link = title_cell.find('a')
            if title_link:
                paper_data['title'] = title_link.text.strip()
                paper_data['link'] = title_link.get('href', '')
                # Get abstract using title
                paper_data['abstract'] = self.get_abstract(paper_data['title'])
            else:
                paper_data['title'] = title_cell.find('strong').text.strip() if title_cell.find('strong') else title_cell.text.strip()
                paper_data['link'] = ''
                paper_data['abstract'] = ''

        # Extract authors
        authors_div = title_cell.find('div', class_='indented')
        if authors_div:
            authors = [author.strip() for author in authors_div.text.split('·')]
            paper_data['authors'] = authors

        # Extract session information
        session_info = title_cell.find(text=lambda text: text and 'Poster Session' in text)
        if session_info:
            paper_data['session'] = session_info.strip()

        return paper_data

    def crawl_accepted_papers(self) -> List[Dict]:
        """Crawl the accepted papers page and extract paper information."""
        papers = []
        url = f"{self.base_url}/Conferences/2025/AcceptedPapers"
        
        print("Fetching CVPR 2025 papers page...")
        html_content = self.fetch_page(url)
        if not html_content:
            return papers

        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table')
        if not table:
            print("Could not find papers table")
            return papers

        # Skip header rows
        rows = table.find_all('tr')[3:]  # Skip first 3 rows
        
        print(f"Found {len(rows)} papers. Starting to parse and fetch abstracts...")
        for row in tqdm(rows, desc="Processing papers"):
            try:
                paper_data = self.parse_paper(row)
                if paper_data and paper_data.get('title'):  # Only add if we have at least a title
                    papers.append(paper_data)
            except Exception as e:
                print(f"Error parsing row: {str(e)}")
                continue

        return papers

    def save_to_json(self, papers: List[Dict], output_file: str = "cvpr2025_papers.json"):
        """Save the crawled papers to a JSON file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
            print(f"Successfully saved {len(papers)} papers to {output_file}")
        except Exception as e:
            print(f"Error saving to JSON: {str(e)}")

def main():
    crawler = CVPR2025Crawler()
    papers = crawler.crawl_accepted_papers()
    crawler.save_to_json(papers)

if __name__ == "__main__":
    main() 