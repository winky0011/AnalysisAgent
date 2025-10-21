from typing import Dict, Any
from langchain_core.tools import tool
from common import get_neo4j_db_manager, get_embeddings_model
import ast
from langchain_community.vectorstores import Neo4jVector
from typing import List, Callable, Any, Dict
from tqdm import tqdm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

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
    向量检索工具函数：从Neo4j知识图谱中检索与查询相关的多维度信息
    
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
    
    # 解析LangChain返回的文档内容
    tmp = docs[0].page_content
    result_data = ast.literal_eval(docs[0].page_content)
    return {
        "chunks": [item["text"] for item in result_data["Chunks"]],  # 提取文本块内容
        "reports": result_data["Reports"],  # 社区报告列表
        "relationships": [rel["descriptionText"] for rel in result_data["Relationships"]],  # 关系描述
        "entities": [ent["descriptionText"] for ent in result_data["Entities"]]  # 实体描述
    }

def map_reduce_search(
    query: str,
    level: int,
    llm: Any,
    map_system_prompt: str,
    reduce_system_prompt: str,
    response_type: str = "多个段落",
    data_query: str = """
        MATCH (c:__Community__)
        WHERE c.level = $level
        RETURN {communityId:c.id, full_content:c.full_content} AS output
    """,
    map_process_func: Callable = None,
    reduce_process_func: Callable = None
) -> str:
    """
    基于Map-Reduce模式的知识图谱搜索工具函数
    
    参数:
        query: 用户查询语句
        level: 社区层级
        llm: 大语言模型实例
        map_system_prompt: Map阶段的系统提示词
        reduce_system_prompt: Reduce阶段的系统提示词
        response_type: 最终响应格式类型
        data_query: 获取数据的Cypher查询语句
        map_process_func: 自定义Map处理函数（可选）
        reduce_process_func: 自定义Reduce处理函数（可选）
    
    返回:
        str: 最终整合的答案
    """
    # 获取数据库连接（复用单例的DBConnectionManager）
    db_manager = get_neo4j_db_manager()
    graph = db_manager.get_graph()

    # 1. 数据获取阶段 - 获取指定层级的社区数据
    def _get_data(level: int) -> List[dict]:
        return graph.query(
            data_query,
            params={"level": level}
        )

    # 2. Map阶段 - 处理单条数据生成中间结果
    def _default_map_process(item: dict) -> str:
        map_prompt = ChatPromptTemplate.from_messages([
            ("system", map_system_prompt),
            ("human", "---数据---\n{context_data}\n\n用户问题：{question}")
        ])
        map_chain = map_prompt | llm | StrOutputParser()
        return map_chain.invoke({
            "question": query,
            "context_data": item["output"]
        })

    # 3. Reduce阶段 - 整合中间结果生成最终答案
    def _default_reduce_process(intermediate_results: List[str]) -> str:
        reduce_prompt = ChatPromptTemplate.from_messages([
            ("system", reduce_system_prompt),
            ("human", "---中间结果---\n{report_data}\n\n用户问题：{question}\n\n请以{response_type}格式输出答案")
        ])
        reduce_chain = reduce_prompt | llm | StrOutputParser()
        return reduce_chain.invoke({
            "report_data": "\n\n".join(intermediate_results),
            "question": query,
            "response_type": response_type
        })

    # 执行数据获取
    data_items = _get_data(level)
    if not data_items:
        return "未找到相关数据"

    # 执行Map阶段（使用自定义函数或默认函数）
    map_func = map_process_func if map_process_func else _default_map_process
    intermediate_results = []
    for item in tqdm(data_items, desc="Map阶段处理中"):
        try:
            result = map_func(item)
            intermediate_results.append(result)
        except Exception as e:
            print(f"处理数据项出错: {str(e)}")

    # 执行Reduce阶段（使用自定义函数或默认函数）
    reduce_func = reduce_process_func if reduce_process_func else _default_reduce_process
    try:
        final_result = reduce_func(intermediate_results)
    except Exception as e:
        return f"整合结果出错: {str(e)}"

    return final_result


def get_neo4j_tools():
    return [
        vector_search
    ]
