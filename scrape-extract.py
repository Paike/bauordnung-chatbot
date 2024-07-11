import requests
from bs4 import BeautifulSoup
import os
import re
from dotenv import load_dotenv

def format_title(title):
    """Extracts the title number and additional text, formats it as 'Paragraph X bzw. § X Additional Text'."""
    match = re.match(r'^\s*§\s*(\d+)(\s*\(.*?\))?(.*)', title)
    if match:
        number = match.group(1)
        additional_text = match.group(3).strip()
        formatted_title_complete = f"Paragraph {number} bzw. § {number} {additional_text}"
        formatted_title = f"§ {number} {additional_text}"
        return formatted_title_complete, formatted_title
    return None, None

def clean_filename(filename):
    """Cleans and formats the filename to be filesystem-friendly."""
    filename = re.sub(r'[^\w\s-]', '', filename)
    filename = filename.strip().replace(' ', '_')
    return filename

def scrape_and_save(url, output_dir):
    """Scrapes the given URL and saves the paragraphs to separate text files."""
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    elements = soup.find_all('p', class_='lrdetail')

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for element in elements:
        title = element.get_text(strip=True)
        formatted_title_complete, formatted_title = format_title(title)
        if formatted_title is None:
            continue

        title_number = re.search(r'\d+', formatted_title).group(0)
        filename = clean_filename(f"paragraph_{title_number}") + ".txt"

        next_element = element.find_next_sibling()
        content = []
        while next_element and (next_element.name != 'h2' and (next_element.name != 'p' or 'lrdetail' not in next_element.get('class', []))):
            content.append(next_element.get_text(strip=True))
            next_element = next_element.find_next_sibling()

        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"## {formatted_title}\n")
            file.write('\n'.join(content))
            file.write(f"\n\n(Dies ist der Inhalt von {formatted_title_complete})")

def main():

    load_dotenv()

    url = os.getenv('SCRAPE_URL')
    output_dir = os.getenv('SCRAPE_FOLDER')
    
    if not url or not output_dir:
        raise ValueError("Environment variables SCRAPER_URL and OUTPUT_DIR must be set.")
    
    scrape_and_save(url, output_dir)

if __name__ == "__main__":
    main()