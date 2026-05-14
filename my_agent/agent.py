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

root_agent = Agent(
    model="gemini-2.5-flash",
    name="itba_academic_assistant",
    description="Asistente académico virtual del ITBA.",
    instruction=SYSTEM_INSTRUCTION,
    generate_content_config=GenerateContentConfig(
        safety_settings=[
            SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
            SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
            SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
            SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
        ]
    ),
    tools=[
        search_knowledge_base,
        enroll_in_subject,
        get_my_enrollments,
        get_subject_enrollments,
        escalate_to_academic_advisor,
    ],
)
