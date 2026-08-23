import os
import json
import dotenv
import chromadb
from pathlib import Path
from datetime import datetime
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.cohere import CohereEmbedding
from llama_index.core import Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext, VectorStoreIndex

dotenv.load_dotenv()
key = os.getenv("COHERE_API_KEY")

catalog_path = "data/knowledge_base/catalog.json"
descriptions_path = "data/knowledge_base/descriptions.json"
degree_rules_path = "data/knowledge_base/degree_rules.json"



# Data Loading
def load_and_merge_data(catalog_path: str, descriptions_path: str, degree_rules_path: str):
    """
    merge catalog & descriptions and load degree_rules
    """
    print("\n⌛ Loading data files...")

    # reading knowledge_base files
    with open(catalog_path, 'r', encoding='utf-8') as f:
        catalog = json.load(f)
        
    with open(descriptions_path, 'r', encoding='utf-8') as f:
        descriptions = json.load(f)
        
    with open(degree_rules_path, 'r', encoding='utf-8') as f:
        degree_rules = json.load(f)

    # search for each course description with its code
    description_dict = {item['course_code']: item['description'] for item in descriptions}

    # extract core course from data
    core_courses = set(degree_rules.get("core_requirements", []))

    # num of courses with weird & poisoned instructions
    dropped_courses = 0

    # where we'll keep all our merged data
    documents = []

    # marge catalog & descriptions and build our documents
    for course in catalog:
        course_code = course['course_code']
        description_text = description_dict.get(course_code, "No description available.")
        credits_val = int(course.get("credits", 0))
        department_val = str(course.get("department", ""))

        # any course with hours more than 4 will be dropped
        if credits_val > 4 or credits_val <= 0:
            print(f"🚨 [SECURITY ALERT] Dropping {course_code}: Invalid credits ({credits_val})")
            dropped_courses += 1
            continue
            
        # letters of any departement is no longer than 50 or drop it
        if len(department_val) > 50:
            print(f"🚨 [SECURITY ALERT] Dropping {course_code}: Department name too long (Prompt Injection suspected)")
            dropped_courses += 1
            continue

        # read each course info from courses descriptions
        text_content = f"Course: {course['title']}\nDescription: {description_text}"

        # any course inside the degree_rules core courses will be core, else will be elective
        course_type = "core" if course_code in core_courses else "elective"

        # preparing metadata
        # convert Lists and Objects to Strings so the ChromDB accepts it
        metadata = {
            "course_code": course_code,
            "level": int(course["level"]),
            "credits": int(course["credits"]),
            "department": course["department"],
            "course_type": course_type,
            "prerequisites": ",".join(course["prerequisites"]) if course["prerequisites"] else "None",
            "schedule_days": ",".join(course["schedule"]["days"]),
            "schedule_start": course["schedule"]["start_time"],
            "schedule_end": course["schedule"]["end_time"]
        }

        # because we have bombs in our data so we added it as a note in our metadata
        if "note" in course["schedule"]:
            metadata["schedule_note"] = course["schedule"]["note"]

        # build our documents
        doc = Document(
            id_=course_code,
            text=text_content,
            metadata=metadata,
        )
        documents.append(doc)

    print(f"🎯 Successfully created {len(documents)} Documents.\n")
    return documents, degree_rules, dropped_courses


# Chunking
def create_nodes(documents):
    """
    split documents and turn them into chunks
    """
    print("⌛ Splitting documents into chunks...")

    # because our description is short nearly from 2 to 3 sentences
    parser = SentenceSplitter(chunk_size=256, chunk_overlap=20)
    chunks = parser.get_nodes_from_documents(documents)
    
    print(f"🎯 Successfully created {len(chunks)} Chunk from {len(documents)} Documents.\n")
    
    return chunks


# Embedding
def setup_embeddings(api_key: str, target_input_type: str = "search_document"):
    """
    converting chunks into vectors
    """
    print(f"⌛ Setting up Cohere Embedding Model (Mode: {target_input_type})...")
    
    if not api_key:
        raise ValueError("Cohere API Key is missing! Check your .env file.")

    embed_model = CohereEmbedding(
        cohere_api_key=api_key,
        model_name="embed-english-v3.0",
        input_type=target_input_type,
        embed_batch_size=90 
    )
    
    Settings.embed_model = embed_model
    
    print("🎯 Cohere Embedding Model is ready!\n")
    return embed_model


# vectorDB
def setup_vector_database(documents, chunks, embed_model):
    """
    Building the ChromaDB vector store (Wipes existing data and rebuilds from scratch)
    """
    print("⌛ Setting up ChromaDB and VectorStoreIndex...")
    persist_dir = "./chroma_db"
    db = chromadb.PersistentClient(path=persist_dir)
    collection_name = "course_catalog"

    try:
        db.get_collection(collection_name)
        print("🧹 Existing database found. Wiping it clean for a fresh rebuild...")
        db.delete_collection(collection_name)
    except Exception:
        print("🗂️  No existing database found.")

    print("⌛ Building from scratch using chunks...")
    chroma_collection = db.create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    index = VectorStoreIndex(
        nodes=chunks, 
        storage_context=storage_context,
        embed_model=embed_model
    )
    
    storage_context.persist(persist_dir=persist_dir)
    
    print("🎯 Vector Database is successfully built and populated!\n")
    return index


if __name__ == "__main__":
    documents, degree_rules, dropped_courses = load_and_merge_data(catalog_path, descriptions_path, degree_rules_path)
    print(f"🧹 Dropped {dropped_courses} poisoned/invalid course(s) during ingestion.")
    chunks = create_nodes(documents)
    embed_model = setup_embeddings(key, target_input_type="search_document")
    setup_vector_database(documents, chunks, embed_model)