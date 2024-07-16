import langroid as lr
from langroid.language_models.base import (
    LLMResponse,
    LLMMessage,
    Role,
)
import re
from langroid.utils.constants import NO_ANSWER
import chainlit as cl

# langroid/chainlit overrides
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
    cl.run_sync(step.send())


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
    cl.run_sync(step.send())  # type: ignore


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
            return self.agent.config.name + f"({lr.agent.callbacks.chainlit.AGENT})"
        case "user":
            if self.config.user_has_agent_name:
                return self.agent.config.name + f"({lr.agent.callbacks.chainlit.YOU})"
            else:
                return lr.agent.callbacks.chainlit.YOU
        case _:
            return self.agent.config.name + f"({entity})"

# base.py prompts are in english, and llm rephrases german questions to english
# def my_generate(self, prompt: str, max_tokens: int = 200) -> LLMResponse:
#     pass