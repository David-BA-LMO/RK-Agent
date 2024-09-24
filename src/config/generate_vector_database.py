#CARGA DE DOCUMENTOS PDF
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
import os
import sys
current_script_path = os.path.abspath(__file__)
app_directory_path = os.path.dirname(os.path.dirname(current_script_path))
sys.path.append(app_directory_path)
from directories import PDF_dir, DB_DIR



#-----------------------------------------------------------------------------------------------------

#CARGA DE DOCUMENTOS PDF
def get_pdf_docs(PDF_dir):
    """
    Genera una lista de textos a partir de archivos PDF en un directorio.

    Parametros:
        - PDF_dir: String indicando la localización del directorio de pdfs.

    Devuelve:
        - list_docs: Lista de Documents, uno por cada página (no por documento). Cada uno contiene page_content y algunos metadatos.
    """
    loader = PyPDFDirectoryLoader(PDF_dir)
    list_docs = loader.load()
    return list_docs


#DIVISIÓN EN CHUNKS
def get_docs_chunk(list_docs):
    """
    Divide una lista de Documents en chunks de texto más pequeños.

    Parámetros:
        - list_docs: Lista de Documents. Cada elemento representa un documento.

    Devuelve:
        - chunked_docs: Lista de chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 800,
        chunk_overlap = 100,
        add_start_index = True
    )
    chunked_docs = text_splitter.split_documents(list_docs)
    return chunked_docs


embeddings = OpenAIEmbeddings()
list_docs = get_pdf_docs(PDF_dir)
print("Número de páginas cargadas: ", len(list_docs))
chunked_docs = get_docs_chunk(list_docs)
print("Número de chunks generados: ", len(chunked_docs))
db = FAISS.from_documents(chunked_docs, embeddings) #FAISS.from_documents ya que los chunks tienen un contenido y metadata.
db.save_local(DB_DIR)
print(db.index.ntotal)

#local_index.merge_from(faiss_db) Para incorporar nueva información
#local_index.save_local(FAISS_USERGUIDE_INDEX)

