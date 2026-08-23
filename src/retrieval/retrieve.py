import os
import sys
import subprocess
from typing import Any, Dict, List, Optional, Union

import chromadb
import dotenv
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters
from llama_index.vector_stores.chroma import ChromaVectorStore

from src.retrieval.ingest import setup_embeddings
from src.schemas import QueryFilterSchema


dotenv.load_dotenv()
key = os.getenv("COHERE_API_KEY")


# load Vector Database
def load_existing_index():
    """
    load the existing ChromaDB vector index from local disk storage.
    """
    print("\n⌛ Loading existing Vector Database...")
    persist_dir = "./chroma_db"

    # check if the data exist
    if not os.path.exists(persist_dir):
        print("⚠️ Vector database not found! Running ingest.py to build it...\n")
        try:
            subprocess.run([sys.executable, "-m", "src.retrieval.ingest"], check=True)
            print("\n✅ Running ingest.py complete! Resuming retrieval setup...\n")
        except subprocess.CalledProcessError as e:
            raise RuntimeError("❌ Failed to build the database. Please check ingest.py for errors.") from e

    # connect to the vectorDB
    db = chromadb.PersistentClient(path=persist_dir)
    chroma_collection = db.get_collection("course_catalog")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=persist_dir
    )

    # load embeding model
    embed_model = setup_embeddings(key, target_input_type="search_query")
    
    # get the index from the vectorDB
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        storage_context=storage_context,
        embed_model=embed_model
    )
    
    print("🎯 Index loaded successfully!\n")
    return index



# metadata filter builder
def build_metadata_filters(
    query_filters: Union[QueryFilterSchema, Dict[str, Any]]) -> Optional[MetadataFilters]:
    """
    turn the condition we extract from the student query into strict filter rules.
    """
    if isinstance(query_filters, QueryFilterSchema):
        query_filters = query_filters.model_dump(exclude_none=True)

    filters_list = []

    # filter courses <= the student level
    if query_filters.get("level") is not None:
        filters_list.append(
            MetadataFilter(key="level", value=int(query_filters["level"]), operator=FilterOperator.EQ)
        )

    # filter by min_credit hours in the degree rules
    if query_filters.get("min_credits") is not None:
        filters_list.append(
            MetadataFilter(key="credits", value=int(query_filters["min_credits"]), operator=FilterOperator.GTE)
        )

    # filter on max credit hours
    safe_max_credits = 4
    if query_filters.get("max_credits") is not None:
        safe_max_credits = min(int(query_filters["max_credits"]), 8)

    filters_list.append(
        MetadataFilter(key="credits", value=safe_max_credits, operator=FilterOperator.LTE)
    )
    print(f"[Security] Enforced safe max_credits limit: {safe_max_credits}")

    # filter based on the department
    if query_filters.get("department"):
        filters_list.append(
            MetadataFilter(key="department", value=str(query_filters["department"]), operator=FilterOperator.EQ)
        )

    # filter by course type (core, elective, any)
    if query_filters.get("course_type") and query_filters["course_type"] != "any":
        filters_list.append(
            MetadataFilter(key="course_type", value=str(query_filters["course_type"]), operator=FilterOperator.EQ)
        )

    # filter by course_code
    if query_filters.get("course_code"):
        filters_list.append(
            MetadataFilter(key="course_code", value=str(query_filters["course_code"]), operator=FilterOperator.EQ)
        )

    if filters_list:
        return MetadataFilters(filters=filters_list, condition="and")
    
    return None



# normalize days so if can be searched using Sat, Sun, etc.
def normalize_days(value: Any) -> List[str]:
    if value is None: return []
    if isinstance(value, list): return [str(d).strip() for d in value if str(d).strip()]
    if isinstance(value, str): return [d.strip() for d in value.split(",") if d.strip()]
    return [str(value).strip()]

# get the days of the required course
def get_course_schedule_days(node: NodeWithScore) -> List[str]:
    return normalize_days(node.node.metadata.get("schedule_days"))

def time_ranges_overlap(course_start: str, course_end: str, unavailable_start: str, unavailable_end: str) -> bool:
    return course_start < unavailable_end and unavailable_start < course_end

def has_schedule_conflict(node: NodeWithScore, unavailable_days: List[str], unavailable_time: Optional[Dict[str, Any]]) -> bool:
    course_days = get_course_schedule_days(node)
    
    if not unavailable_days: return False
    shared_days = set(course_days) & set(unavailable_days)
    if not shared_days: return False
    if unavailable_time is None: return True

    unavailable_start = unavailable_time.get("start")
    unavailable_end = unavailable_time.get("end")
    if unavailable_start is None or unavailable_end is None: return True

    course_start = str(node.node.metadata.get("schedule_start"))
    course_end = str(node.node.metadata.get("schedule_end"))
    if course_start == "None" or course_end == "None": return True

    return time_ranges_overlap(course_start, course_end, unavailable_start, unavailable_end)

def apply_schedule_constraints(nodes: List[NodeWithScore], query_filters: Union[QueryFilterSchema, Dict[str, Any]]) -> List[NodeWithScore]:
    if isinstance(query_filters, QueryFilterSchema):
        query_filters = query_filters.model_dump()

    unavailable_days = query_filters.get("unavailable_days", [])
    unavailable_time = query_filters.get("unavailable_time")

    if not unavailable_days:
        return nodes

    return [node for node in nodes if not has_schedule_conflict(node, unavailable_days, unavailable_time)]


# filtered semantic retrieval
def retrieve_courses(index, query_str: str, 
    query_filters: Optional[Union[QueryFilterSchema, Dict[str, Any]]] = None, 
    top_k: int = 5
):
    """
    search the vector database using semantic search and strict metadata filters.
    """
    print(f"\n🔍 Searching for: '{query_str}'")
    
    filters = None # store the courses we found that match the query filters
    filters_data = None # store the filters, we got from the query

    if query_filters is not None:
        # prepare data to get filtred, extract info from query
        if isinstance(query_filters, QueryFilterSchema):
            filters_data = query_filters.model_dump(exclude_none=True)
        else:
            filters_data = query_filters

        print(f"⚙️ Applying metadata filters: {filters_data}")
        filters = build_metadata_filters(filters_data)
    else:
        print("⚪ No metadata filters applied. Pure semantic search.")

    retriever = index.as_retriever(similarity_top_k=top_k, filters=filters)
    nodes = retriever.retrieve(query_str)

    print(f"🎯 Semantic retrieval found {len(nodes)} matching courses.")

    # apply schdule filter
    if filters_data is not None:
        before_schedule_filter = len(nodes)
        nodes = apply_schedule_constraints(nodes=nodes, query_filters=filters_data)
        removed_courses = before_schedule_filter - len(nodes)
        
        if removed_courses > 0:
            print(f"📅 Schedule filtering removed {removed_courses} conflicting courses.")

    print(f"✅ Returning {len(nodes)} valid courses.")
    return nodes