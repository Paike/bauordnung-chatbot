import langroid as lr
from langroid.agent.special.doc_chat_agent import DocChatAgent, DocChatAgentConfig
from langroid.utils.configuration import settings as langroid_settings
import langroid.parsing.parser as lp


import chainlit as cl
from chainlit.logger import logger

import os
import logging
from logging.handlers import TimedRotatingFileHandler
import datetime
from textwrap import dedent

import src.overrides as overrides
from src.tools import DocumentTool
import src.constants as c
import src.prompts as prompts

langroid_settings.debug = c.SETTINGS_DEBUG

# make ui names nicer
lr.agent.callbacks.chainlit.YOU = c.USER_NAME
lr.agent.callbacks.chainlit.LLM = c.LLM_NAME
lr.agent.callbacks.chainlit.SYSTEM = c.FRONT_CHAT_AGENT_NAME
lr.agent.callbacks.chainlit.AGENT = c.FRONT_CHAT_AGENT_NAME

# set up logging
log_folder = c.LOGS_FOLDER
os.makedirs(log_folder, exist_ok=True)

logger.setLevel(logging.INFO)

log_filename = os.path.join(
    log_folder, datetime.datetime.now().strftime('bot_%Y-%m-%d.log'))
file_handler = TimedRotatingFileHandler(
    log_filename, when='midnight', interval=1, backupCount=14)
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

# define welcome message, is sent first to the user
async def my_add_instructions(
    title: str = 'Bauordnungsbot',
    content: str = dedent(
        '''
        # Landesbauordnung 2018 (BauO NRW 2018)
        
        ## Ich beantworte Ihre Fragen zur Landesbauordnung 2018 (BauO NRW 2018)

        Stellen Sie mir einfach Ihre Fragen, wie zum Beispiel 
        - "wo wird ein notwendiger Flur definiert?" 
        - "ab wieviel Etagen muss ein Gebäude einen Aufzug besitzen?"
        - "kann ich einfach so eine Neonschild aufstellen?"

        [Quelle: BauO NRW 2018](https://recht.nrw.de/lmi/owa/br_text_anzeigen?v_id=74820170630142752068)
        '''
    ),
    author: str = 'Bauordnungsbot',
) -> None:
    await cl.Message(
        author='Bauordnungsbot',
        content='',
        elements=[
            cl.Text(
                name=title,
                content=content,
                display='inline',
            )
        ],
    ).send()


@cl.on_chat_start
async def on_chat_start():
    await my_add_instructions()

    # agent for extracting and summarizing the documents
    doc_agent = DocChatAgent(
        DocChatAgentConfig(
            system_message=prompts.doc_chat_system_message,
            user_message=prompts.doc_chat_instructions,
            summarize_prompt=prompts.doc_chat_summarize_prompt,
            cache=False,
            debug=True,
            conversation_mode=False,
            relevance_extractor_config=None,
            use_bm25_search=True,
            split=True,
            name=c.DOC_CHAT_AGENT_NAME,
            n_query_rephrases=0,
            hypothetical_answer=False,
            n_neighbor_chunks=3,
            vecdb=lr.vector_store.ChromaDBConfig(
                storage_path=".chroma/bauordnung/",
                replace_collection=False,
                cloud=False,
            ),  
            # vecdb=lr.vector_store.QdrantDBConfig(
            #     collection_name='bauordnung',
            #     replace_collection=False,
            #     storage_path='.qdrant/data/',
            #     cloud=False
            # ),
            cross_encoder_reranking_model='',
            parsing=lp.ParsingConfig(  # modify as needed
                n_similar_docs=1,
                chunk_size=500,  # aim for this many tokens per chunk
                # splitter=lr.parsing.parser.Splitter.SIMPLE,
                # token_encoding_model='BAAI/bge-large-en-v1.5',
                pdf=lp.PdfParsingConfig(
                    library='fitz'
                )
            )
        )
    )
    doc_agent.ingest_doc_paths(c.DOCUMENTS_FOLDER)

    # agent for communicating with the user
    config = lr.ChatAgentConfig(
        name=c.FRONT_CHAT_AGENT_NAME,
        system_message=prompts.chat_system_message
    )
    front_agent = lr.ChatAgent(config)
    front_agent.enable_message(lr.agent.tools.RecipientTool)
    front_agent.enable_message(DocumentTool)

    # define tasks for getting documents summarization and answers
    doc_task = lr.Task(
        doc_agent,
        name=c.DOC_CHAT_AGENT_NAME,
        done_if_no_response=[lr.Entity.LLM],  # done if null response from LLM
        done_if_response=[lr.Entity.LLM],  # done if non-null response from LLM
    )

    front_agent_task = lr.Task(
        front_agent,
        interactive=True
    )

    front_agent_task.add_sub_task([doc_task])

    cl.user_session.set('task', front_agent_task)
    cl.user_session.set('agent', front_agent)


@cl.on_message
async def on_message(message: cl.Message):
    front_agent_task = cl.user_session.get('task')
    front_agent = cl.user_session.get('agent')

    callback_config = lr.ChainlitCallbackConfig(
        user_has_agent_name=False,
        show_subtask_response=True
    )
    # have to add German to some prompts
    # lr.language_models.base.generate = overrides.my_generate

    lr.ChainlitAgentCallbacks(front_agent, message, callback_config)

    # we override some functions to change the output
    lr.ChainlitAgentCallbacks._entity_name = overrides.my_entity_name
    lr.ChainlitAgentCallbacks.show_agent_response = overrides.my_show_agent_response

    lr.ChainlitTaskCallbacks.show_subtask_response = overrides.my_show_subtask_response
    lr.ChainlitTaskCallbacks(front_agent_task, message, callback_config)

    await front_agent_task.run_async(message.content)
