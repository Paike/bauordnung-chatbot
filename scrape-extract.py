import os
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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

def save_as_text(filepath, title, content):
    """Saves the content to a text file."""
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(f"## {title}\n")
        file.write('\n'.join(content))
        file.write(f"\n\n(Dies ist der Inhalt von {title})")

def save_as_pdf(filepath, title, content):
    """Saves the content to a PDF file."""
    filepath = f"{filepath}.pdf"
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica", 12)
    text = c.beginText(40, height - 40)
    text.setFont("Helvetica-Bold", 14)
    text.textLine(f"## {title}")
    text.setFont("Helvetica", 12)
    text.textLines('\n'.join(content))
    text.textLine(f"\n\n(Dies ist der Inhalt von {title})")

    c.drawText(text)
    c.showPage()
    c.save()

def scrape_and_save(url, output_dir, output_format):
    """Scrapes the given URL and saves the paragraphs to separate files."""
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
        filename = clean_filename(f"paragraph_{title_number}")
        filepath = os.path.join(output_dir, filename)

        next_element = element.find_next_sibling()
        content = []
        while next_element and (next_element.name != 'h2' and (next_element.name != 'p' or 'lrdetail' not in next_element.get('class', []))):
            content.append(next_element.get_text(strip=True))
            next_element = next_element.find_next_sibling()

        if output_format == 'pdf':
            save_as_pdf(filepath, formatted_title, content)
        elif output_format == 'txt':
            save_as_text(filepath + '.txt', formatted_title, content)
        else:
            raise ValueError("Unsupported output format. Use 'pdf' or 'txt'.")

def main():
    load_dotenv()

    url = os.getenv('SCRAPE_URL')
    output_dir = os.getenv('SCRAPE_FOLDER')
    output_format = os.getenv('OUTPUT_FORMAT', 'txt').lower()
    
    if not url or not output_dir:
        raise ValueError("Environment variables SCRAPER_URL and SCRAPE_FOLDER must be set.")
    
    if output_format not in ['pdf', 'txt']:
        raise ValueError("Environment variable OUTPUT_FORMAT must be 'pdf' or 'txt'.")

    scrape_and_save(url, output_dir, output_format)

if __name__ == "__main__":
    main()
