import requests
from bs4 import BeautifulSoup
import json
import time
from typing import List, Dict, Optional
from tqdm import tqdm
import urllib.parse
import random
from fake_useragent import UserAgent
import re

class GoogleScholarCrawler:
    def __init__(self):
        self.base_url = "https://scholar.google.com"
        self.ua = UserAgent()
        self.session = requests.Session()
        
    def _get_random_headers(self):
        """Generate random headers for each request."""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
    def get_citation_count(self, title: str, authors: List[str]) -> Dict:
        """Get citation count from Google Scholar."""
        try:
            # Add delay to avoid being blocked
            time.sleep(random.uniform(2, 4))
            
            # Create search query with title and first author
            query = f"{title} {authors[0]}"
            encoded_query = urllib.parse.quote(query)
            search_url = f"{self.base_url}/scholar?q={encoded_query}"
            
            response = self.session.get(
                search_url,
                headers=self._get_random_headers(),
                timeout=10
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all paper entries
            print(query)
            for result in soup.find_all('div', class_='gs_ri'):
                print(result)
                paper_title = result.find('h3', class_='gs_rt')
                if not paper_title:
                    continue
                    
                # Clean the title text
                found_title = paper_title.get_text().lower().strip()
                searched_title = title.lower().strip()
                
                # Check if titles match approximately
                if self._similar_titles(found_title, searched_title):
                    # Find citation count
                    citation_div = result.find('div', class_='gs_fl')
                    if citation_div:
                        citation_text = citation_div.get_text()
                        match = re.search(r'Cited by (\d+)', citation_text)
                        print(match)
                        if match:
                            return {
                                'citation_count': int(match.group(1)),
                                'google_scholar_url': self.base_url + citation_div.find('a')['href'] if citation_div.find('a') else None
                            }
            
            return {
                'citation_count': 0,
                'google_scholar_url': None
            }
            
        except Exception as e:
            print(f"Error fetching Google Scholar citation count for {title}: {str(e)}")
            return {
                'citation_count': 0,
                'google_scholar_url': None
            }
            
    def _similar_titles(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """Check if two titles are similar using simple ratio."""
        # Remove special characters and extra spaces
        title1 = re.sub(r'[^\w\s]', '', title1.lower())
        title2 = re.sub(r'[^\w\s]', '', title2.lower())
        
        # Use set intersection to check similarity
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        intersection = words1.intersection(words2)
        shorter_length = min(len(words1), len(words2))
        
        if shorter_length == 0:
            return False
            
        similarity = len(intersection) / shorter_length
        return similarity >= threshold

class CVPRCrawler:
    def __init__(self, base_url: str = "https://cvpr.thecvf.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': UserAgent().random
        })
        self.scholar_crawler = GoogleScholarCrawler()
        
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
                time.sleep(2 ** attempt)
        return None

    def parse_paper(self, row) -> Dict:
        """Parse a single paper row from the table."""
        paper_data = {}
        
        # Extract title and link if available
        title_cell = row.find('td')
        if title_cell:
            title_link = title_cell.find('a')
            if title_link:
                paper_data['title'] = title_link.text.strip()
                paper_data['link'] = title_link.get('href', '')
            else:
                paper_data['title'] = title_cell.find('strong').text.strip() if title_cell.find('strong') else title_cell.text.strip()
                paper_data['link'] = ''

        # Extract authors
        authors_div = title_cell.find('div', class_='indented')
        if authors_div:
            authors = [author.strip() for author in authors_div.text.split('·')]
            paper_data['authors'] = authors

        # Extract session information
        session_info = title_cell.find(text=lambda text: text and 'Poster Session' in text)
        if session_info:
            paper_data['session'] = session_info.strip()

        # Extract location
        location_cell = row.find_all('td')[-1]
        if location_cell:
            paper_data['location'] = location_cell.text.strip()

        return paper_data

    def process_paper_with_citations(self, paper: Dict) -> Dict:
        """Process a single paper by adding citation information."""
        citation_info = self.scholar_crawler.get_citation_count(paper['title'], paper['authors'])
        paper.update(citation_info)
        return paper

    def crawl_accepted_papers(self) -> List[Dict]:
        """Crawl the accepted papers page and extract paper information."""
        papers = []
        url = f"{self.base_url}/Conferences/2024/AcceptedPapers"
        
        html_content = self.fetch_page(url)
        if not html_content:
            return papers

        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table')
        if not table:
            print("Could not find papers table")
            return papers

        # Skip header rows
        rows = table.find_all('tr')[3:]
        
        print("Parsing papers...")
        for row in tqdm(rows, desc="Parsing papers"):
            try:
                paper_data = self.parse_paper(row)
                if paper_data and paper_data.get('title'):
                    papers.append(paper_data)
            except Exception as e:
                print(f"Error parsing row: {str(e)}")
                continue

        # Process papers sequentially with progress bar
        print("\nFetching citation information from Google Scholar...")
        processed_papers = []
        for paper in tqdm(papers, desc="Processing papers"):
            processed_papers.append(self.process_paper_with_citations(paper))

        # Sort papers by citation count
        processed_papers.sort(key=lambda x: x.get('citation_count', 0), reverse=True)
        return processed_papers

    def save_to_json(self, papers: List[Dict], output_file: str = "cvpr2024_papers.json"):
        """Save the crawled papers to a JSON file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
            
            total_citations = sum(paper.get('citation_count', 0) for paper in papers)
            print(f"\nSummary Statistics:")
            print(f"Total number of papers: {len(papers)}")
            print(f"Total citations: {total_citations}")
            print(f"Average citations per paper: {total_citations/len(papers):.2f}")
            print(f"\nTop 10 most cited papers:")
            for i, paper in enumerate(papers[:10], 1):
                print(f"{i}. {paper['title']}")
                print(f"   Citations: {paper.get('citation_count', 0)}")
                print(f"   Authors: {', '.join(paper['authors'])}")
                print(f"   Google Scholar URL: {paper.get('google_scholar_url', 'N/A')}")
                print()
                
        except Exception as e:
            print(f"Error saving to JSON: {str(e)}")

def main():
    crawler = CVPRCrawler()
    papers = crawler.crawl_accepted_papers()
    crawler.save_to_json(papers)

if __name__ == "__main__":
    main()