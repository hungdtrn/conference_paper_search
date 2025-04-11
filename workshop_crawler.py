import requests
from bs4 import BeautifulSoup
import json

# URL of the webpage
url = 'https://cvpr.thecvf.com/Conferences/2025/workshop-list'

# Send a GET request to the URL
response = requests.get(url)

# Check if the request was successful
if response.status_code == 200:
    html_content = response.text
    # print(html_content)
    soup = BeautifulSoup(html_content, 'html.parser')
    # print(soup)
    # Find all topic sections
    topics = soup.find_all('td', class_='pt-4 pb-2')
    # print(topics)
    workshops_by_topic = {}

    for i, topic in enumerate(topics):
        topic_name = topic.get_text(strip=True)
        print("-------------", topic_name, "-------------")
        
        workshop_dict = {}
        next_topic = topics[i + 1] if i + 1 < len(topics) else None
        current_tr = topic.find_next('tr')
        
        while current_tr and (next_topic is None or current_tr != next_topic.find_previous('tr')):
            td_cnt = 0
            for _, td in enumerate(current_tr.find_all('td')):
                tmp_text = td.get_text(strip=True)
                if tmp_text in ["IEEE Computer Society", "The Computer Vision Foundation"]:
                    break
                if tmp_text and td_cnt % 2 == 0:
                    print(tmp_text)
                    workshop_dict[tmp_text] = {
                        "url":"",
                        "abstract": ""
                    }
                    td_cnt += 1

            workshops = current_tr.find_all('a')

            for workshop in workshops:
                if workshop['href'] and workshop['href'].startswith('mailto:'):
                    continue
                    
                workshop_name = workshop.get_text(strip=True)
                if workshop_name == "IEEE Computer Society" or workshop_name == "The Computer Vision Foundation":
                    break

                workshop_dict[workshop_name]["url"] = workshop['href']
            
            current_tr = current_tr.find_next('tr')
        # print(workshop_list)
        workshops_by_topic[topic_name] = workshop_dict

    # Print the workshops by topic
    for topic, workshops in workshops_by_topic.items():
        print(f"\nTopic: {topic}")
        for workshop, info in workshops.items():
            print(f"  - {workshop}: {info['url']}")

    # Save the workshops by topic to a JSON file
    with open('workshops_by_topic.json', 'w') as f:
        json.dump(workshops_by_topic, f, indent=4)
else:
    print(f"Failed to retrieve the page. Status code: {response.status_code}")