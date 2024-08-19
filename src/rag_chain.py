from langchain.tools.retriever import create_retriever_tool
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
    SystemMessagePromptTemplate)
from src.utilities import *
from src.directories import RAG_CHAIN_PROMPT_dir, RAG_AGENT_DESCRIPTION_dir, DB_DIR
from src.config.base_models import generate_rag_llm

#-------------------------------------------------------------------------------------------------


RAG_CHAIN_PROMPT = txt_to_str(filepath = RAG_CHAIN_PROMPT_dir)
RAG_AGENT_DESCRIPTION = txt_to_str(filepath = RAG_AGENT_DESCRIPTION_dir) 


class RagChain:

    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vector_db = FAISS.load_local(DB_DIR, self.embeddings, allow_dangerous_deserialization=True)
        self.retriever = self.vector_db.as_retriever(search_kwargs={"k": 4})
        self.tools = [self.generate_retriever_tool()]
        self.llm = generate_rag_llm()
        self.memory = self.generate_memory()
        self.full_prompt = self.generate_prompt()


    # HERRAMIENTA DE RECUPERACIÓN
    def generate_retriever_tool(self):
        retriever_tool = create_retriever_tool(
            self.retriever,
            "retriever_tool",
            "Útil para búsqueda de información en una base de datos vectorial",
        )
        return retriever_tool


    # MEMORIA
    def generate_memory(self):
        memory = ConversationBufferWindowMemory(
                    input_key="input",
                    k=4,
                    memory_key="memory",
                    output_key='output',
                )
        return memory


    # PROMPT
    def generate_prompt(self):
        #Prompt para albergar la memoria
        memory_prompt_template = "\n\nConversación previa: {memory}"
        memory_prompt = PromptTemplate(
                    input_variables=["memory"], 
                    template = memory_prompt_template
            )
        #Prompt final
        full_prompt = ChatPromptTemplate.from_messages(
                [   ("system", RAG_CHAIN_PROMPT),   #Instrucciones de uso de la base de datos
                    SystemMessagePromptTemplate(prompt = memory_prompt),    #Historial de conversación previo
                    ("human", "{input}"),   #Input del usurio
                    MessagesPlaceholder("agent_scratchpad"),    #Historial de acciones del agente
                ]
            )
        return full_prompt
    
    # FUNCIÓN PARA REALIZAR UNA CONSULTA RAG
    def query_rag(self, user_input):
        # Llenar el prompt con la memoria actual y el input del usuario
        prompt = self.full_prompt.format(
            memory=self.memory.load_memory(),  # Cargar la memoria actual
            input=user_input  # Pasar el input del usuario
        )

        # Realizar la consulta al modelo LLM con el prompt completado
        response = self.llm(prompt, tools=self.tools, memory=self.memory)

        # Actualizar la memoria con la interacción reciente
        self.memory.save_context({"input": user_input}, {"output": response})

        return response