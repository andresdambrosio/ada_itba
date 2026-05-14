"""Indexa los documentos de la base de conocimiento. Ejecutar antes de levantar el agente."""

from pathlib import Path
from dotenv import load_dotenv
from my_agent.rag import knowledge_base

load_dotenv(Path(__file__).parent / "my_agent" / ".env")

if __name__ == "__main__":
    print("Indexando documentos...")
    total = knowledge_base.build_index()
    print(f"Listo. {total} chunks indexados en chroma_db/")
