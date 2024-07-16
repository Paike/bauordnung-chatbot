import langroid as lr
from langroid.agent.tool_message import ToolMessage
import fitz
import src.constants as c

class DocumentTool(ToolMessage):
    request: str = "document"
    purpose: str = "To present the content of a legal section with the section number <section_number>."
    folder: str = c.DOCUMENTS_FOLDER
    section_number: str = 1

    def handle(self) -> str:

        filename = f"{self.folder}/paragraph_{self.section_number}.pdf"
        pdf_document = fitz.open(filename)
        markdown_lines = []

        # Iterate through each page
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            text = page.get_text("text")
            lines = text.split('\n')

            for line in lines:
                if line.strip():  # If the line is not empty
                    markdown_lines.append(line)
                else:
                    markdown_lines.append("\n")  # Add a new paragraph

        # Join the markdown lines into a single string
        markdown_content = "\n".join(markdown_lines)
        return f"""
        {markdown_content}
        """