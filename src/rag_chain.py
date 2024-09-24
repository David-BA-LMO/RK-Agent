from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import FAISS
from operator import itemgetter
from langchain_openai import OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from src.utilities import *
from src.directories import RAG_CHAIN_PROMPT_dir, DB_DIR
from src.config.base_models import generate_rag_llm

#-------------------------------------------------------------------------------------------------


RAG_CHAIN_PROMPT = txt_to_str(filepath = RAG_CHAIN_PROMPT_dir)


class RagChain:

    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vector_db = FAISS.load_local(DB_DIR, self.embeddings, allow_dangerous_deserialization=True)
        self.retriever = self.vector_db.as_retriever(search_kwargs={"k": 4}) # 4 documentos de texto a recuperar
        self.rag_prompt = PromptTemplate.from_template(RAG_CHAIN_PROMPT)
        self.rag_llm = generate_rag_llm()
        """
         - Se toma el input del usuario y se selecciona la información relevante.
         - Esa información se pasa al retriever, que busca datos relevantes en la base de datos vectorial
         - Tanto el input del usuario como los datos recuperados y el historial se pasan al prompt de RAG
         - El prompt pasa a través de un modelo de lenguaje
         - Finalmente, la respuesta se procesa como una cadena de texto que se puede mostrar o usar en la aplicación.
         """
        self.rag_chain = {"context": itemgetter("input") | self.retriever, "input": RunnablePassthrough(), "history": RunnablePassthrough()} | self.rag_prompt | self.rag_llm | StrOutputParser()


    # FUNCIÓN PARA REALIZAR UNA CONSULTA RAG
    async def query_rag(self, input: str, history: str) -> str:
        response = await self.rag_chain.ainvoke({"input": input, "history": history})
        return response