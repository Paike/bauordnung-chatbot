#!/bin/bash
python scrape_extract.py
chainlit run -h --port $CHAINLIT_PORT bauordnung_chatbot.py