from langchain.prompts import PromptTemplate
from langchain.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_community.chat_message_histories import ChatMessageHistory
from src.utilities import *
from src.directories import CLASSIFICATION_PROMPT_dir, welcome_message
from src.qa_chain import QAChain
from src.rag_chain import RagChain
from src.config.base_models import generate_router_llm


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
        self.enrouting_chain = {"route": self.classification_chain, "input": lambda x: x["input"]} | RunnableLambda(self.route) # Cadena de enrutamiento
    
    
    def route(self, info):
        if "búsqueda" in info["route"]:
            self.qa_chain.check_last_query(info["input"], info["history"])
        elif "información" in info["route"]:
            self.rag_chain.query_rag(info["input"])
        else:
            return "Esto es off-topic"
    

    def execute_chatbot(self, input):
        class_output = self.classification_chain.invoke({"input": input, "history": self.history.messages})
        # Variable para recoger la salida. Esta puede ser una lista
        responses = None
        
        if class_output == "búsqueda":
            # Activamos herramienta de búsqueda en base de datos
            responses = self.qa_chain.check_last_query(input, self.history)

        elif class_output == "información":
            # Activamos herramienta de recuperación de información
            responses = "Esto es información"
        else:
            # 
            responses = "Esto es off-topic"

        #Agregamos historial de mensajes
        print("Input del cliente:", input["input"])
        self.history.add_user_message(input["input"])
        for response in responses:
            self.history.add_ai_message(response)

        # Devolvemos siempre el último mensaje de respuesta
        return responses[-1]


