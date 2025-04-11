import requests 
from bs4 import BeautifulSoup
from typing import List, Tuple

def get_cvpr_day_links(year: int) -> List[Tuple[str, str]]:
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

# Example usage
if __name__ == "__main__":
    day_links = get_cvpr_day_links(2018)
    
    print("CVPR Conference Days:")
    for date, url in day_links:
        print(f"Date: {date}")
        print(f"URL: {url}")
        print()