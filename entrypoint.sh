#!/bin/bash
python scrape-extract.py
chainlit run -h --port $CHAINLIT_PORT bauordnung-chatbot.py