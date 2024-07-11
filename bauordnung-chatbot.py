import os
import re
import chainlit as cl
import langroid as lr
import langroid.parsing.parser as lp
from langroid.agent.special.doc_chat_agent import DocChatAgent, DocChatAgentConfig
from langroid.utils.constants import NO_ANSWER
from langroid.agent.callbacks.chainlit import (
    add_instructions,
    make_llm_settings_widgets,
    setup_llm,
    update_llm,
    get_text_files,
    SYSTEM,
    ChainlitCallbackConfig
)
from textwrap import dedent
from langroid.language_models.openai_gpt import OpenAIGPT
import langroid.language_models as lm
from langroid.utils.configuration import settings
from dotenv import load_dotenv
import logging
from logging.handlers import TimedRotatingFileHandler
import datetime

lr.agent.callbacks.chainlit.YOU = YOU = "Ihre Frage"
lr.agent.callbacks.chainlit.LLM = LLM = "LLM"
lr.agent.callbacks.chainlit.SYSTEM = SYSTEM = "Bauordnungsbot"
lr.agent.callbacks.chainlit.AGENT = AGENT = "Bauordnungsbot"

settings.debug = False


log_folder = 'logfiles'
os.makedirs(log_folder, exist_ok=True)

logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

log_filename = os.path.join(log_folder, datetime.datetime.now().strftime('bot_%Y-%m-%d.log'))
file_handler = TimedRotatingFileHandler(
    log_filename, when='midnight', interval=1, backupCount=14)
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

system_message = """
You are a helpful assistant, helping me understand a collection of extracts from the document "Bauordnung NRW". Antworte auf deutsch.
"""

summarize_prompt = f"""

        Use the provided extracts (with sources) to answer the QUESTION. 
        If there's not enough information, say so. Use only the 
        information in these extracts, even if your answer is factually incorrect, 
        and even if the answer contradicts other parts of the document. The only 
        important thing is that your answer is consistent with and supported by the 
        extracts. 
        Compose your complete answer, inserting CITATIONS in MARKDOWN format
        [^i][^j] where i,j,... are incrementing NUMBERS starting with 1.
        Always try to include the complete corresponding legal paragraph with your answer.
        Politely refuse if the question has nothing to do with Bauordnung.
        Antworte auf deutsch und in formaler Sprache (Sie).
                
        NUMBERED EXTRACTS:
        
        {{extracts}}
        
        QUESTION:
        {{question}}

""".strip()


async def initialize_agent() -> None:
    # llm_config = lm.OpenAIGPTConfig(
    #     min_output_tokens=100,
    #     max_output_tokens=1200)
    llm_config = lm.OpenAIGPTConfig()
    vecdb_config = lr.vector_store.ChromaDBConfig(
        storage_path=".chroma/data/",
        replace_collection=False,
        # cloud=False,
    )
    config = DocChatAgentConfig(
        system_message=system_message,
        summarize_prompt=summarize_prompt,
        split=False,
        name="Bauordnungsbot",
        vecdb=vecdb_config,
        n_query_rephrases=1,
        hypothetical_answer=False,
        n_neighbor_chunks=5,
        llm=llm_config,
        parsing=lp.ParsingConfig(  # modify as needed
            n_similar_docs=1,
            chunk_size=3000,  # aim for this many tokens per chunk
            # splitter=lr.parsing.parser.Splitter.SIMPLE,
        ),
    )
    agent = DocChatAgent(config)

    relative_path = os.getenv('SCRAPE_FOLDER')
    absolute_path = os.path.abspath(relative_path)

    agent.ingest_doc_paths(absolute_path)

    cl.user_session.set("agent", agent)


async def my_add_instructions(
    title: str = "Instructions",
    content: str = "Enter your question/response in the dialog box below.",
    author: str = "Author",
) -> None:
    await cl.Message(
        author="Bauordnungsbot",
        content="",
        elements=[
            cl.Text(
                name=title,
                content=content,
                display="inline",
            )
        ],
    ).send()


@cl.on_chat_start
async def on_chat_start():
    await my_add_instructions(
        title="Bauordnungsbot",
        author="Bauordnungsbot",
        content=dedent(
            """
        # Landesbauordnung 2018 (BauO NRW 2018)
        
        ## Ich beantworte Ihre Fragen zur Landesbauordnung 2018 (BauO NRW 2018)

        Stellen Sie mir einfach Ihre Fragen, wie zum Beispiel "wo wird ein notwendiger Flur definiert?" oder "ab wieviel Etagen muss ein Gebäude einen Aufzug besitzen?"

        [Quelle: BauO NRW 2018](https://recht.nrw.de/lmi/owa/br_text_anzeigen?v_id=74820170630142752068)
        """
        ),
    )

    cl.user_session.set("callbacks_inserted", False)
    await initialize_agent()


def my_entity_name(
    self, entity: str, tool: bool = False, cached: bool = False
) -> str:
    """Construct name of entity to display as Author of a step"""
    tool_indicator = " =>  🛠️" if tool else ""
    cached = "(cached)" if cached else ""
    match entity:
        case "llm":
            model = self.agent.config.llm.chat_model
            return (

                self.agent.config.name
            )
        case "agent":
            return self.agent.config.name + f"({AGENT})"
        case "user":
            if self.config.user_has_agent_name:
                return self.agent.config.name + f"({YOU})"
            else:
                return YOU
        case _:
            return self.agent.config.name + f"({entity})"


@cl.on_message
async def on_message(message: cl.Message):
    agent: DocChatAgent = cl.user_session.get("agent")

    if not cl.user_session.get("callbacks_inserted", False):
        callback_config = ChainlitCallbackConfig(
            user_has_agent_name=False
        )

        lr.ChainlitAgentCallbacks._entity_name = my_entity_name

        lr.ChainlitAgentCallbacks(agent, message, callback_config)

    logger.info(f"User: {message.content}")

    response: lr.ChatDocument | None = await cl.make_async(agent.llm_response)(
        message.content
    )

    logger.info(f"Bot: {response.content}")
