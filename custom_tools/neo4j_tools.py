from langchain_core.tools import tool
from common import get_neo4j_db_manager, get_embeddings_model
import re
from langchain_community.vectorstores import Neo4jVector
from typing import List, Callable, Any, Dict, Annotated
from tqdm import tqdm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from common.memory_state import MapReduceState
from langgraph.prebuilt import InjectedState

@tool
def vector_search(
    query: str,
    index_name: str = "vector",
    top_entities: int = 10,
    top_chunks: int = 3,
    top_communities: int = 3,
    top_outside_rels: int = 10,
    top_inside_rels: int = 10,
) -> Dict[str, Any]:
    """
    向量检索工具函数：在知识图谱中匹配最相似的实体、文本块等局部信息，适用于精准查询，例如查找与特定主题直接相关的信息、实体间的关系等。
    
    参数:
        query: 用户查询文本
        index_name: Neo4j向量索引名称
        top_entities: 检索的实体数量上限
        top_chunks: 检索的文本块数量上限
        top_communities: 检索的社区数量上限
        top_outside_rels: 实体外部关系数量上限
        top_inside_rels: 实体内部关系数量上限
    
    返回:
        结构化检索结果，包含chunks、reports、relationships、entities四个key
    """
    # 1. 获取全局单例DB连接管理器
    db_manager = get_neo4j_db_manager()
    embeddings = get_embeddings_model()
    
    # 2. 构建Cypher检索模板
    retrieval_query = f"""
    WITH collect(node) as nodes
    WITH
    collect {{
        UNWIND nodes as n
        MATCH (n)<-[:MENTIONS]-(c:__Chunk__)
        WITH distinct c, count(distinct n) as freq
        RETURN {{id:c.id, text: c.text}} AS chunkText
        ORDER BY freq DESC
        LIMIT {top_chunks}
    }} AS text_mapping,
    collect {{
        UNWIND nodes as n
        MATCH (n)-[:IN_COMMUNITY]->(c:__Community__)
        WITH distinct c, c.community_rank as rank, c.weight AS weight
        RETURN c.summary 
        ORDER BY rank, weight DESC
        LIMIT {top_communities}
    }} AS report_mapping,
    collect {{
        UNWIND nodes as n
        MATCH (n)-[r]-(m:__Entity__) 
        WHERE NOT m IN nodes
        RETURN r.description AS descriptionText
        ORDER BY r.weight DESC 
        LIMIT {top_outside_rels}
    }} as outsideRels,
    collect {{
        UNWIND nodes as n
        MATCH (n)-[r]-(m:__Entity__) 
        WHERE m IN nodes
        RETURN r.description AS descriptionText
        ORDER BY r.weight DESC 
        LIMIT {top_inside_rels}
    }} as insideRels,
    collect {{
        UNWIND nodes as n
        RETURN n.description AS descriptionText
    }} as entities
    RETURN {{
        Chunks: text_mapping, 
        Reports: report_mapping, 
        Relationships: outsideRels + insideRels, 
        Entities: entities
    }} AS text, 1.0 AS score, {{}} AS metadata
    """
    
    # 3. 初始化Neo4jVector
    vector_store = Neo4jVector.from_existing_index(
        embedding=embeddings,
        url=db_manager.neo4j_uri,
        username=db_manager.neo4j_username,
        password=db_manager.neo4j_password,
        index_name=index_name,
        retrieval_query=retrieval_query
    )
    
    # 4. 执行相似度搜索
    docs = vector_store.similarity_search(
        query=query,
        k=top_entities,
        params={
            "topChunks": top_chunks,
            "topCommunities": top_communities,
            "topOutsideRels": top_outside_rels,
            "topInsideRels": top_inside_rels,
        }
    )
    
    # 5. 解析结果（处理空结果，返回结构化数据）
    if not docs:
        return {
            "chunks": [],
            "reports": [],
            "relationships": [],
            "entities": []
        }
    
    # 提取原始文本内容
    content = docs[0].page_content.strip()
    
    # 定义解析函数：按标题分割内容
    def parse_section(title, content):
        # 用正则匹配标题后的内容（直到下一个标题或结束）
        pattern = re.compile(rf"{title}:\s*(.*?)(?=\n\w+:|$)", re.DOTALL)
        match = pattern.search(content)
        if not match:
            return []
        # 提取列表项（去除"- "前缀和空行）
        items = [
            item.strip() 
            for item in match.group(1).split("\n") 
            if item.strip().startswith("- ")
        ]
        # 去除每个项的"- "前缀
        return [item[2:].strip() for item in items if item[2:].strip()]
    
    # 解析Entities
    entities = parse_section("Entities", content)
    
    # 解析Reports
    reports = parse_section("Reports", content)
    
    # 解析Relationships（过滤None值）
    relationships = [
        rel for rel in parse_section("Relationships", content) 
        if rel != "None"
    ]
    
    # 解析Chunks（特殊处理：提取text字段）
    chunks = []
    chunks_match = re.search(r"Chunks:\s*(.*?)(?=\n\w+:|$)", content, re.DOTALL)
    if chunks_match:
        # 匹配每个chunk的text字段（处理多行字符串）
        chunk_texts = re.findall(r"'text':\s*'(.*?)'", chunks_match.group(1), re.DOTALL)
        # 清洗文本（去除换行符和多余空格）
        chunks = [
            text.replace("\n", " ").replace("  ", " ").strip() 
            for text in chunk_texts
        ]
    
    return {
        "chunks": chunks,
        "reports": reports,
        "relationships": relationships,
        "entities": entities
    }


def get_neo4j_tools():
    return [
        vector_search
    ]
