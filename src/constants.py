import os

DOCUMENTS_FOLDER = os.path.abspath(os.getenv('SCRAPE_FOLDER'))
DOC_CHAT_AGENT_NAME = os.getenv('DOC_CHAT_AGENT_NAME')
FRONT_CHAT_AGENT_NAME = os.getenv('FRONT_CHAT_AGENT_NAME')
LLM_NAME = os.getenv('LLM_NAME')
USER_NAME = os.getenv('USER_NAME')
SETTINGS_DEBUG = os.getenv('DEBUG', default='True') 
LOGS_FOLDER = os.getenv('LOGS_FOLDER', default='logfiles')