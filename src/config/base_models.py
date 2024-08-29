from langchain_openai import ChatOpenAI
import openai
import os
from dotenv import load_dotenv


load_dotenv()
openai_key = os.getenv("OPEN_AI_API_KEY")


#GENERACIÓN DEL MODELO DE LENGUAJE PARA ROUTER
def generate_router_llm():
    llm = ChatOpenAI(
        model="gpt-4-turbo-2024-04-09", 
        temperature = 0,
        openai_api_key=openai_key
    )
    return llm

# GENERACIÓN DEL MODELO DE LENGUAJE PARA CHEQUEO DE CONSULTAS
def generate_check_llm():
    openai.api_key = openai_key
    return "gpt-4o-mini"

#GENERACIÓN DEL MODELO DE LENGUAJE PARA QA
def generate_qa_llm():
    llm = ChatOpenAI(
        model="gpt-4-turbo-2024-04-09", 
        temperature = 0,
        openai_api_key=openai_key
    )
    return llm

#GENERACIÓN DEL MODELO DE LENGUAJE PARA RAG
def generate_rag_llm():
    llm = ChatOpenAI(
        temperature = 0, 
        model= 'gpt-3.5-turbo',
        openai_api_key=openai_key
    )
    return llm