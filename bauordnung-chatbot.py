import langroid as lr
import chainlit as cl
from chainlit import run_sync
from langroid.agent.special.doc_chat_agent import DocChatAgent, DocChatAgentConfig
import langroid.parsing.parser as lp
import re
import logging
from chainlit.logger import logger
import os
import textwrap

from langroid.agent.callbacks.chainlit import add_instructions
from textwrap import dedent
from langroid.utils.configuration import settings
from logging.handlers import TimedRotatingFileHandler
import datetime
import fitz
from langroid.utils.constants import NO_ANSWER, DONE, SEND_TO, PASS

from langroid.language_models.base import (
    LLMMessage,
    Role,
)


DOC_CHAT_AGENT = "Dokumenten-Agent"
FRONT_CHAT_AGENT = "Bauordnungsbot"
lr.agent.callbacks.chainlit.YOU = YOU = "Ihre Frage"
lr.agent.callbacks.chainlit.LLM = LLM = "LLM"
lr.agent.callbacks.chainlit.SYSTEM = SYSTEM = FRONT_CHAT_AGENT
lr.agent.callbacks.chainlit.AGENT = AGENT = FRONT_CHAT_AGENT

settings.debug = True


log_folder = 'logfiles'
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

relative_path = os.getenv('SCRAPE_FOLDER')
absolute_path = os.path.abspath(relative_path)
print(absolute_path)


class DocumentTool(lr.ToolMessage):
    request = "document"
    purpose = "To present the content of a legal section with the section number <section_number>."
    section_number: str

    def handle(self) -> str:

        filename = f"{absolute_path}/paragraph_{self.section_number}.pdf"
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


# class MyChainlitAgentCallbacks(lr.ChainlitAgentCallbacks):
#     def show_llm_response(
#         self,
#         content: str,
#         is_tool: bool = False,
#         cached: bool = False,
#         language: str | None = None,
#     ) -> None:
#         """Show non-streaming LLM response."""
#         print("MyChainlitAgentCallback")
#         step = cl.Step(
#             id=self.curr_step.id if self.curr_step is not None else None,
#             name=self._entity_name("llm", tool=is_tool, cached=cached),
#             type="llm",
#             parent_id=self._get_parent_id(),
#             language=language or ("json" if is_tool else None),
#         )
#         self.last_step = step
#         self.curr_step = None
#         step.output = textwrap.dedent(content) or NO_ANSWER
#         self.parent_agent.message_history.extend(
#             [
#                 LLMMessage(role=Role.ASSISTANT, content=content)
#             ])
#         logger.info(
#             f"""
#             Showing NON-STREAM LLM response for {self.agent.config.name}
#             id = {step.id}
#             under parent {self._get_parent_id()}
#             """
#         )
#         run_sync(step.send())  # type: ignore

# Was sagt die Bauordnung zum BEstandsschutz?
def my_show_subtask_response(
    self, task: lr.Task, content: str, is_tool: bool = False
) -> None:
    """Show sub-task response as a step, nested at the right level."""
    self.agent.message_history.extend(
        [
            LLMMessage(role=Role.ASSISTANT, content=content)
        ])
    # The step should nest under the calling agent's last step
    step = cl.Step(
        name=self.task.agent.config.name +
        f"( ⏎ via {task.agent.config.name})",
        type="run",
        parent_id=self._get_parent_id(),
        language="json" if is_tool else None,
    )
    content = "Ich konnte keine korrekte Antwort finden, bitte formulieren Sie Ihre Frage anders." if "DO-NOT-KNOW" in content else content
    content = re.sub(r'Role\.[^\)]*\):', '', content).strip()
    step.output = content or NO_ANSWER
    self.last_step = step
    run_sync(step.send())


def my_show_agent_response(self, content: str, language="") -> None:
    print("CONTENT:")
    print(content)
    self.agent.message_history.extend(
        [
            LLMMessage(role=Role.ASSISTANT, content=content)
        ])
    language = ""
    step = cl.Step(
        id=self.curr_step.id if self.curr_step is not None else None,
        name=self._entity_name("llm") + "(⏎ via Function-Call)",
        type="llm",
        parent_id=self._get_parent_id(),
        language=language,
    )
    # if language == "text":
    #     content = wrap_text_preserving_structure(content, width=90)
    self.last_step = step
    self.curr_step = None
    step.output = content
    logger.info(
        f"""
        Showing CUSTOM AGENT response for {self.agent.config.name}
        id = {step.id} 
        under parent {self._get_parent_id()}
        """
    )
    run_sync(step.send())  # type: ignore


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


async def my_add_instructions(
    title: str = "Bauordnungsbot",
    content: str = dedent(
        """
        # Landesbauordnung 2018 (BauO NRW 2018)
        
        ## Ich beantworte Ihre Fragen zur Landesbauordnung 2018 (BauO NRW 2018)

        Stellen Sie mir einfach Ihre Fragen, wie zum Beispiel "wo wird ein notwendiger Flur definiert?" oder "ab wieviel Etagen muss ein Gebäude einen Aufzug besitzen?"

        [Quelle: BauO NRW 2018](https://recht.nrw.de/lmi/owa/br_text_anzeigen?v_id=74820170630142752068)
        """
    ),
    author: str = "Bauordnungsbot",
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
    await my_add_instructions()

    doc_chat_instructions = """
    You will be given various passages from this document and shall summarize them into
     coherent answers. Always give a detailed answer, containing a summary of the passage.
    """

    system_message = """
    You are a helpful assistant, helping me understand a collection of extracts from the legal document 
    "Bauordnung NRW". 
    Antworte auf deutsch und formal (Sie)
    """

    summarize_prompt = f"""

        Use the provided NUMBERED extracts (with sources)  to answer the QUESTION. 
        If there's not enough information, respond with {NO_ANSWER}. Use only the 
        information in these extracts, even if your answer is factually incorrect, 
        and even if the answer contradicts other parts of the document. 
        If the source contains a legal section number, include it in your response.
        The only important thing is that your answer is consistent with and supported by the 
        extracts. Compose your complete answer, inserting CITATIONS in MARKDOWN format
        [^i][^j] where i,j,... are the extract NUMBERS you are 
        citing.
        For example your answer might look like this (NOTE HOW multiple citations
        are grouped as [^2][^5]):
        
        Beethoven composed the 9th symphony in 1824.[^1] After that he became deaf
        and could not hear his own music. [^2][^5]. He was a prolific composer and
        wrote many famous pieces.
        
        NUMBERED EXTRACTS:
        
        {{extracts}}
        
        QUESTION:
        {{question}}

    """.strip()

    doc_agent = DocChatAgent(
        DocChatAgentConfig(
            system_message=system_message,
            user_message=doc_chat_instructions,
            summarize_prompt=summarize_prompt,
            cache=False,
            debug=True,
            conversation_mode=False,
            relevance_extractor_config=None,
            use_bm25_search=True,
            split=True,
            name=DOC_CHAT_AGENT,
            n_query_rephrases=0,
            hypothetical_answer=False,
            n_neighbor_chunks=3,
            vecdb=lr.vector_store.QdrantDBConfig(
                collection_name="bauordnung",
                replace_collection=False,
                storage_path=".qdrant/data/",
                cloud=False

            ),
            cross_encoder_reranking_model="",
            parsing=lp.ParsingConfig(  # modify as needed
                n_similar_docs=1,
                chunk_size=500,  # aim for this many tokens per chunk
                # splitter=lr.parsing.parser.Splitter.SIMPLE,
                # token_encoding_model="BAAI/bge-large-en-v1.5",
                pdf=lp.PdfParsingConfig(
                    library="unstructured"
                )
            )
        )
    )
    doc_agent.ingest_doc_paths(absolute_path)
    # doc_agent.enable_message(DocumentTool)

    doc_task = lr.Task(
        doc_agent,
        name=DOC_CHAT_AGENT,
        done_if_no_response=[lr.Entity.LLM],  # done if null response from LLM
        done_if_response=[lr.Entity.LLM],  # done if non-null response from LLM
        # Don't use system_message here since it will override doc chat agent's
        # default system message
    )
# THEN you will break down the question into individual components and simplify it into a new question.
#         Reformulate nouns, for example, "Strohdächer" becomes "Dach aus Stroh," "Brandschutzmauer" becomes "Mauer zum Brandschutz."
    config = lr.ChatAgentConfig(
        name=FRONT_CHAT_AGENT,
        system_message=f"""
        You are a legal expert with the name "Bauordnungsbot", answering my (the user) questions about
        the legal document Bauordnung (of the state Northrhine-Westphalia) described in a certain document, and you do NOT have access to this document.

        FIRST look into your chat history for the answer.

        Identify the main object in the question and rephrase the question with three synonyms to it.
        THEN you will use the 'recipient_message' tool/function to ask the "{DOC_CHAT_AGENT}" this question to give a short summary about the topic. 
        Address your request to the {DOC_CHAT_AGENT} using the 'recipient_message' tool/function.

        IF the user asks for the content of a specific legal section, use the correct section number <section_number>, 
        receive the content from the `document` tool/function-call and present it to the user.    

        Example for such a question: "Zeig mir den Paragrafen 34"    

        Antworte auf deutsch und formal (Sie)
         """,
    )
    agent = lr.ChatAgent(config)
    agent.enable_message(lr.agent.tools.RecipientTool)
    agent.enable_message(DocumentTool)

    task_config = lr.TaskConfig(
    )

    task = lr.Task(
        agent,
        interactive=True,
        config=task_config
    )

    task.add_sub_task([doc_task])
    # MyChainlitAgentCallbacks(agent)
    cl.user_session.set("task", task)
    cl.user_session.set("agent", agent)


@cl.on_message
async def on_message(message: cl.Message):
    task = cl.user_session.get("task")
    agent: lr.ChatAgent = cl.user_session.get("agent")
    # if not cl.user_session.get("callbacks_inserted", False):
    callback_config = lr.ChainlitCallbackConfig(
        user_has_agent_name=False,
        show_subtask_response=True
    )

    lr.ChainlitAgentCallbacks(agent, message, callback_config)
    lr.ChainlitAgentCallbacks._entity_name = my_entity_name
    lr.ChainlitAgentCallbacks.show_agent_response = my_show_agent_response
    lr.ChainlitTaskCallbacks.show_subtask_response = my_show_subtask_response

    lr.ChainlitTaskCallbacks(task, message, callback_config)
    # await task.run_async(message.content)
    # await cl.make_async(task.run)()
    response: lr.ChatDocument | None = await cl.make_async(task.run)(
        message.content
    )
