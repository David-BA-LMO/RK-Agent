from langchain.prompts import PromptTemplate
from langchain.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_community.chat_message_histories import ChatMessageHistory
from src.utilities import *
from src.directories import CLASSIFICATION_PROMPT_dir, welcome_message
from src.qa_chain import QAChain
from src.rag_chain import RagChain
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
        self.history = ChatMessageHistory()
        self.history.add_ai_message(welcome_message) #Memoria de mensajes
        self.classification_chain = self.classification_prompt | self.llm | StrOutputParser() #Cadena clasificadora
        self.enrouting_chain = {"route": self.classification_chain, "input": lambda x: x["input"], "history": lambda x: x["history"] } | RunnableLambda(self.route) # Cadena de enrutamiento
    
    
    # Esta función es el paso final de la cadena "enrouting_chain"
    def route(self, info):
        try:
            if "búsqueda" in info["route"]:
                print("Resultado de la clasificación:", info["route"])
                self.qa_chain.check_last_query(info["input"], info["history"])
            elif "información" in info["route"]:
                print("Resultado de la clasificación:", info["route"])
                self.rag_chain.query_rag(info["input"])
            else:
                print("Resultado de la clasificación:", info["route"])
                return "Soy un chatbot especializado en búsquedas de inmuebles"
        except Exception as e:  
            logger.info(f"ERROR: enrouting chain failed", {e})


    def execute_chatbot(self, input):
        responses = self.enrouting_chain.invoke({"input": input, "history": self.history.messages})
        if(responses==None):
           responses = "Lo siento, hubo un problema al procesar tu solicitud."
        print(responses)
        #Agregamos historial de mensajes
        self.history.add_user_message(input)
        if isinstance(responses, list):
            for response in responses:
                self.history.add_ai_message(response)
            return responses[-1]  # Devolver el último mensaje de respuesta
        else:
            self.history.add_ai_message(responses)
            return responses


