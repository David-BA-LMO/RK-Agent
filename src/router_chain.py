from langchain.prompts import PromptTemplate
from langchain.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE
from langchain_core.output_parsers import StrOutputParser
from src.utilities import *
from src.directories import CLASSIFICATION_PROMPT_dir, welcome_dir, PRESENTATION_PROMPT_dir
from src.qa_chain import QAChain
from src.rag_chain import RagChain
from typing import AsyncGenerator, List
from session_manager import SessionData
import logging
from src.config.base_models import generate_router_llm

logger = logging.getLogger(__name__)


class Router_chain:

    def __init__(self):
        self.qa_chain = QAChain()
        self.rag_chain = RagChain()
        self.llm = generate_router_llm()
        self.CLASSIFICATION_PROMPT = txt_to_str(filepath = CLASSIFICATION_PROMPT_dir)
        self.classification_prompt = PromptTemplate.from_template(self.CLASSIFICATION_PROMPT)
        self.classification_chain = self.classification_prompt | self.llm | StrOutputParser() #Cadena clasificadora
        #self.enrouting_chain = {"route": self.classification_chain, "input": lambda x: x["input"], "history": lambda x: x["history"] } | RunnableLambda(self.route) # Cadena de enrutamiento
        self.welcome_document = txt_to_str(welcome_dir)
        self.PRESENTATION_PROMPT = txt_to_str(PRESENTATION_PROMPT_dir)
        self.presentation_prompt = PromptTemplate.from_template(self.PRESENTATION_PROMPT)
        self.presentation_chain = self.presentation_prompt | self.llm | StrOutputParser()
    

    async def execute(self, input: str, session: SessionData) -> AsyncGenerator[str, None]:
        
        history = self.get_conversation_history(session.history, 4) # Accedemos al historial de conversación

        # Cadena enrutadora
        result = await self.classification_chain.ainvoke({"input": input, "history": history})

        if result == "búsqueda":
            async for message in self.qa_chain.execute(input, history, session): # Herramienta Text2SQL
                yield message
        elif result == "información":
            async for message in self.rag_chain.query_rag(input, history): # Herramienta RAG
                yield message
        else:
            async for message in self.presentation_chain.astream({"input": input, "welcome": self.welcome_document}):
                yield message

    
    # Esta función recupera el historial de mensages de la sesión
    def get_conversation_history(self, data: List, k: int) -> str:
        # Ordenamos el diccionario por el campo 'timestamp' en orden descendente
        sorted_entries = sorted(data, key=lambda x: x['timestamp'], reverse=True)[:k]
        sorted_entries.reverse()

        conversation_history = []
        
        for entry in sorted_entries:
            conversation_history.append(f"user: {entry['user']}")
            conversation_history.append(f"bot: {entry['bot']}")
        logger.info("HISTORY: "+str(conversation_history))
        return str(conversation_history)


