import time
import argparse
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException
import os
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

# Load environment variables
load_dotenv()

# Configure Gemini
if "GOOGLE_API_KEY" not in os.environ:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

def analyze_workshop_info(image_path: str) -> str:
    """
    Analyze workshop information from a screenshot using Gemini API.
    
    Args:
        image_path (str): Path to the screenshot image
    
    Returns:
        str: Analysis of the workshop information
    """
    try:
        # Initialize Gemini model
        model = genai.GenerativeModel('gemini-2.0-flash-lite-001')
        
        # Read the image
        image = Image.open(image_path)
        
        # Create the prompt for Gemini
        prompt = """
        Analyze this workshop webpage screenshot and extract the following information in the exact format below:

## Description
[Extract the workshop description/abstract here.]

## Topics (If available)
[Extract the key topics or themes here, one per line with bullet points]

Please maintain this exact format in your response.
"""
        
        # Call Gemini API
        response = model.generate_content([prompt, image])
        return response.text
        
    except Exception as e:
        print(f"Error analyzing workshop information: {e}")
        return None

def capture_full_webpage(url, output_path="webpage_screenshot.png", wait_time=5):
    """
    Captures a screenshot of the entire webpage.
    
    Args:
        url (str): URL of the webpage to screenshot
        output_path (str): Path where the screenshot will be saved
        wait_time (int): Time in seconds to wait for the page to load
    
    Returns:
        tuple: (bool, str) - (True if screenshot was successful, analysis text if available)
    """
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")  # Set initial window size
    
    try:
        # Initialize the Chrome driver
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Set page load timeout
        driver.set_page_load_timeout(60)
        
        # Navigate to the URL
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for the page to load
        print(f"Waiting {wait_time} seconds for page to load completely...")
        time.sleep(wait_time)
        
        # Get the total height of the page
        total_height = driver.execute_script("return document.body.scrollHeight")
        
        # Set the window size to capture the full page
        driver.set_window_size(1920, total_height)
        time.sleep(1)  # Small delay to allow resize to complete
        
        # Take the screenshot
        print("Taking screenshot...")
        driver.save_screenshot(output_path)
        print(f"Screenshot saved to {output_path}")
        
        # Analyze the workshop information
        print("Analyzing workshop information...")
        analysis = analyze_workshop_info(output_path)
        
        # Close the browser
        driver.quit()
        return True, analysis
        
    except TimeoutException:
        print(f"Timeout occurred while loading {url}")
        return False, None
    except WebDriverException as e:
        print(f"WebDriver error: {e}")
        return False, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, None

def process_workshops(json_file_path, output_dir="screenshots"):
    """
    Process workshops from JSON file and update with extracted information.
    
    Args:
        json_file_path (str): Path to the JSON file containing workshops
        output_dir (str): Directory to save screenshots
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the JSON file
    with open(json_file_path, 'r') as f:
        workshops = json.load(f)
    
    # Process each workshop
    for topic, topic_workshops in workshops.items():
        print(f"\nProcessing workshops in topic: {topic}")
        for workshop_name, workshop_info in topic_workshops.items():
            url = workshop_info.get('url', '')
            # if url and not workshop_info.get('abstract'):  # Only process if URL exists and abstract is empty
            if url:
                print(f"\nProcessing workshop: {workshop_name}")
                screenshot_path = os.path.join(output_dir, f"{workshop_name.replace('/', '_')}.png")
                success, analysis = capture_full_webpage(url, screenshot_path)
                
                if success and analysis:
                    # Extract description from analysis
                    description = ""
                    topics = []
                    current_section = None
                    print(analysis)
                    for line in analysis.split('\n'):
                        if line.startswith('## Description'):
                            current_section = 'description'
                        elif line.startswith('## Topics'):
                            current_section = 'topics'
                        elif line.strip() and current_section:
                            if current_section == 'description':
                                description += line.strip() + ' '
                            elif current_section == 'topics':
                                topics.append(line.strip()[2:].strip())
                    
                    # Update workshop info
                    workshop_info['abstract'] = description.strip()
                    if topics:
                        workshop_info['topics'] = topics
                    
                    # Save the updated JSON after each workshop
                    with open(json_file_path, 'w') as f:
                        json.dump(workshops, f, indent=4)
                    print(f"Updated information for {workshop_name} and saved to JSON file")
    
    print("\nAll workshops processed successfully!")

if __name__ == "__main__":
    # Set up command line arguments
    parser = argparse.ArgumentParser(description="Process workshops from JSON file and update with extracted information.")
    parser.add_argument("json_file", help="Path to the JSON file containing workshops")
    parser.add_argument("-o", "--output_dir", default="screenshots", 
                        help="Output directory for screenshots (default: screenshots)")
    
    args = parser.parse_args()
    
    # Process workshops and update JSON
    process_workshops(args.json_file, args.output_dir)