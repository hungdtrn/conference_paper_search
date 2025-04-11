import requests
from bs4 import BeautifulSoup
import json
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote
import re
from typing import List, Tuple

class CVPRCrawler:
    def __init__(self, base_url: str = "https://cvpr.thecvf.com"):
        self.base_url = base_url
        self.session = requests.Session()
        # Add headers to mimic browser behavior
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

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
            # Clean the title for search
            search_title = re.sub(r'[^\w\s]', '', title)
            search_title = ' '.join(search_title.split())
            
            # Search arXiv
            search_url = f"http://export.arxiv.org/api/query?search_query=ti:{quote(search_title)}&max_results=1"
            response = self.session.get(search_url)
            response.raise_for_status()
            
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
        """Get abstract from multiple sources."""
        # Try Semantic Scholar first
        abstract = self.search_semantic_scholar(title)
        if abstract:
            return abstract
            
        # Try arXiv if Semantic Scholar fails
        abstract = self.search_arxiv(title)
        if abstract:
            return abstract
            
        return ""

    def parse_paper(self, row, year) -> Dict:
        """Parse a single paper row from the table."""
        paper_data = {"year": year}
        
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

    def crawl_accepted_papers_new(self, year) -> List[Dict]:
        """Crawl the accepted papers page and extract paper information."""
        papers = []
        url = f"{self.base_url}/Conferences/{year}/AcceptedPapers"
        
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
        
        for row in rows:
            try:
                paper_data = self.parse_paper(row, year)
                if paper_data and paper_data.get('title'):  # Only add if we have at least a title
                    papers.append(paper_data)
            except Exception as e:
                print(f"Error parsing row: {str(e)}")
                continue

        return papers


    def get_cvpr_day_links(self, year: int) -> List[Tuple[str, str]]:
        """
        Fetch and extract day links from CVPR conference website.
        
        Args:
            year: Conference year (e.g., 2018)
            
        Returns:
            List of tuples containing (date, url)
        """
        # Construct base URL
        url = f"https://openaccess.thecvf.com/CVPR{year}"
        
        # Fetch content
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching URL {url}: {e}")
            return []

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the content div and extract day links
        content_div = soup.find('div', id='content')
        day_links = []
        
        if content_div:
            # Find all links containing day parameter
            links = content_div.find_all('a', href=lambda x: x and f'CVPR{year}.py?day=' in x)
            
            for link in links:
                date = link.get_text().split(':')[1].strip()
                url = f"https://openaccess.thecvf.com{link['href']}"
                day_links.append((date, url))
        
        return sorted(day_links)  # Sort by date

    def _crawl_accepted_papers_one_day(self, year, url):
        papers = []
        html_content = self.fetch_page(url)
        if not html_content:
            return papers

        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all paper entries
        # Each paper starts with a dt.ptitle followed by dd elements
        titles = soup.find_all('dt', class_='ptitle')

        for title_element in titles:
            try:
                paper = {"year": year}
                
                # Extract title and link
                title_link = title_element.find('a')
                if title_link:
                    paper['title'] = title_link.text.strip()
                    paper['url'] = urljoin(url, title_link['href'])
                else:
                    continue

                # Find the next dd elements
                dd_elements = title_element.find_next_siblings('dd')
                if not dd_elements:
                    continue

                # First dd contains authors
                authors_dd = dd_elements[0]
                paper['authors'] = []
                author_forms = authors_dd.find_all('form', class_='authsearch')
                for form in author_forms:
                    author_input = form.find('input', {'name': 'query_author'})
                    if author_input:
                        paper['authors'].append(author_input['value'])

                # Second dd contains links
                if len(dd_elements) > 1:
                    links_dd = dd_elements[1]
                    paper['links'] = {}
                    
                    # Find all links
                    links = links_dd.find_all('a')
                    for link in links:
                        text = link.text.strip().lower()
                        if text == 'pdf':
                            paper['links']['pdf'] = urljoin(url, link['href'])
                        elif text == 'supp':
                            paper['links']['supplementary'] = urljoin(url, link['href'])
                        elif text == 'arxiv':
                            paper['links']['arxiv'] = link['href']

                papers.append(paper)
                
            except Exception as e:
                print(f"Error parsing paper: {str(e)}")
                
        return papers
    
    def crawl_accepted_papers_legacy(self, year) -> List[Dict]:
        """Crawl CVPR 2022 papers."""
        papers = []
        url = f"https://openaccess.thecvf.com/CVPR{year}"
        dates = self.get_cvpr_day_links(year)
        if dates:
            for d, _ in dates:
                papers += self._crawl_accepted_papers_one_day(year, url+f"?day={d}")
        else:
            papers = self._crawl_accepted_papers_one_day(year, url+"?day=all")

        return papers

    def crawl_accepted_papers(self, year):
        if year >= 2023:
            papers =  self.crawl_accepted_papers_new(year)
        else:
            papers = self.crawl_accepted_papers_legacy(year)
        print("Crawled {} papers from {}".format(len(papers), year))
        return papers

    def save_to_json(self, papers: List[Dict], output_file: str = "cvpr_papers.json"):
        """Save the crawled papers to a JSON file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
            print(f"Successfully saved {len(papers)} papers to {output_file}")
        except Exception as e:
            print(f"Error saving to JSON: {str(e)}")

def main():
    crawler = CVPRCrawler()
    papers = []
    years = [2025]  # Only crawl 2025
    for year in years:
        papers += crawler.crawl_accepted_papers(year)

    out_title = f"cvpr_paper_{years[0]}.json"
    crawler.save_to_json(papers, out_title)

if __name__ == "__main__":
    main()