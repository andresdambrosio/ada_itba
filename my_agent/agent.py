import os

from google.adk.agents.llm_agent import Agent
from google.genai.types import GenerateContentConfig, HarmBlockThreshold, HarmCategory, SafetySetting

from .prompt import SYSTEM_INSTRUCTION
from .tools import (
    enroll_in_subject,
    escalate_to_academic_advisor,
    get_my_enrollments,
    get_subject_enrollments,
    search_knowledge_base,
)

_MODEL_ENV = os.environ.get("MODEL", "gemini-2.5-flash")

if _MODEL_ENV.startswith("ollama/"):
    from google.adk.models.lite_llm import LiteLlm
    _model = LiteLlm(model=_MODEL_ENV)
    _config = None
else:
    _model = _MODEL_ENV
    _config = GenerateContentConfig(
        safety_settings=[
            SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
            SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
            SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
            SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
        ]
    )

root_agent = Agent(
    model=_model,
    name="itba_academic_assistant",
    description="Asistente académico virtual del ITBA.",
    instruction=SYSTEM_INSTRUCTION,
    generate_content_config=_config,
    tools=[
        search_knowledge_base,
        enroll_in_subject,
        get_my_enrollments,
        get_subject_enrollments,
        escalate_to_academic_advisor,
    ],
)
