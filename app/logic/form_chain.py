import logging
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate
from app.utils.general_utilities import open_txt

from app.logic.tool_config.base_models import generate_router_llm
from app.config import CONFIRM_FORM_PROMPT_dir

logger = logging.getLogger(__name__)

class Form_chain:

    # MODELOS DE LENGUAJE
    llm = generate_router_llm()

    # PLANTILLAS DE PROMPTS
    CONFIRM_FORM_PROMPT = open_txt(CONFIRM_FORM_PROMPT_dir)

    # PROMPTS
    confirm_form_prompt = PromptTemplate.from_template(CONFIRM_FORM_PROMPT)

    # CADENAS 
    confirm_form_chain = confirm_form_prompt | llm | StrOutputParser()  # Cadena para confirmación del envío del formulario 

    @classmethod
    async def execute(cls, personal_data: dict):
            """
            Función que solo se ejecuta tras confirmar y enviar correctamente un formulario de datos personales. Se enruta hacia una cadena específica 
            pensada para informar al usuario del correcto envío de datos.
            """
            try:
                user_name = personal_data.get("username")

                async for partial_message in cls.confirm_form_chain.astream({"user_name": user_name}):
                    yield {"type": "text", "content": partial_message}
                yield {"type": "metadata", "key": "message_source", "content": {"tool": "form_tool", "chain": "confirm_form_chain"}}

            except Exception as e:
                logger.error(f"Unexpected error in personal data form confirmation: {e}")
                raise Exception(f"ERROR: Unexpected error in personal data form confirmation: {e}")