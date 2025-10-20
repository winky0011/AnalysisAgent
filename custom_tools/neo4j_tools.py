from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from common import get_neo4j_db_manager, get_embeddings_model
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from common.get_models import get_embeddings_model

# 获取数据库连接管理器单例
db_manager = get_neo4j_db_manager()
embeddings = get_embeddings_model()

@tool("retrieve_communities_by_property")
def retrieve_communities_by_property(
    property_name: str, 
    property_value: Any,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    根据属性检索社区节点
    
    参数:
        property_name: 社区属性名称（如"name"、"category"）
        property_value: 社区属性值
        limit: 返回结果数量限制
    
    返回:
        符合条件的社区列表，包含节点属性和ID
    """
    cypher = f"""
    MATCH (c:Community)
    WHERE c.{property_name} = $value
    RETURN c.id AS id, c.name AS name, c.description AS description, 
            labels(c) AS labels, properties(c) AS properties
    LIMIT $limit
    """
    
    result = db_manager.execute_query(
        cypher, 
        params={"value": property_value, "limit": limit}
    )
    
    return result.to_dict('records')

@tool("retrieve_communities_by_embedding")
def retrieve_communities_by_embedding(
    query: str,
    similarity_threshold: float = 0.7,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    基于Embedding相似度检索社区
    
    参数:
        query: 检索查询文本
        similarity_threshold: 相似度阈值（0-1之间）
        limit: 返回结果数量限制
    
    返回:
        符合相似度条件的社区列表，包含相似度分数
    """
    # 生成查询向量
    query_embedding = embeddings.embed_query(query)
    
    # Neo4j向量相似度查询（需要社区节点有embedding属性）
    cypher = """
    MATCH (c:Community)
    WHERE c.embedding IS NOT NULL
    WITH c, gds.similarity.cosine(c.embedding, $query_embedding) AS similarity
    WHERE similarity >= $threshold
    RETURN c.id AS id, c.name AS name, c.description AS description,
            similarity, properties(c) AS properties
    ORDER BY similarity DESC
    LIMIT $limit
    """
    
    result = db_manager.execute_query(
        cypher,
        params={
            "query_embedding": query_embedding,
            "threshold": similarity_threshold,
            "limit": limit
        }
    )
    
    return result.to_dict('records')

@tool("retrieve_subcommunities")
def retrieve_subcommunities(
    community_id: str,
    depth: int = 1,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    检索指定社区的子社区（包含层级关系）
    
    参数:
        community_id: 父社区ID
        depth: 检索深度（1表示直接子社区，2表示子社区+孙社区等）
        limit: 每层返回结果数量限制
    
    返回:
        子社区列表，包含层级关系信息
    """
    cypher = f"""
    MATCH (parent:Community)-[r:CONTAINS*1..{depth}]->(child:Community)
    WHERE parent.id = $parent_id
    WITH child, length(r) AS level, r AS relationships
    RETURN child.id AS id, child.name AS name, child.description AS description,
            level AS hierarchy_level, properties(child) AS properties
    LIMIT $limit
    """
    
    result = db_manager.execute_query(
        cypher,
        params={"parent_id": community_id, "limit": limit}
    )
    
    return result.to_dict('records')

@tool("retrieve_community_then_subcommunities")
def retrieve_community_then_subcommunities(
    query: str,
    property_filter: Optional[Dict[str, Any]] = None,
    similarity_threshold: float = 0.7,
    subcommunity_depth: int = 1,
    community_limit: int = 5,
    subcommunity_limit: int = 10
) -> Dict[str, Any]:
    """
    级联检索：先检索符合条件的社区，再检索其下属子社区
    
    参数:
        query: 检索查询文本（用于embedding检索）
        property_filter: 可选的属性过滤条件（如{"category": "tech"}）
        similarity_threshold: embedding相似度阈值
        subcommunity_depth: 子社区检索深度
        community_limit: 主社区检索数量限制
        subcommunity_limit: 每个主社区的子社区数量限制
    
    返回:
        包含主社区及其子社区的层级结构数据
    """
    # 1. 检索主社区（结合属性过滤和embedding检索）
    main_communities = []
    
    if property_filter:
        # 属性过滤检索
        prop_name, prop_value = next(iter(property_filter.items()))
        main_communities = retrieve_communities_by_property(
            property_name=prop_name,
            property_value=prop_value,
            limit=community_limit
        )
    
    # 如果属性检索结果不足，补充embedding检索
    if len(main_communities) < community_limit:
        remaining = community_limit - len(main_communities)
        embedding_results = retrieve_communities_by_embedding(
            query=query,
            similarity_threshold=similarity_threshold,
            limit=remaining
        )
        main_communities.extend(embedding_results)
    
    # 2. 为每个主社区检索子社区
    result = {
        "main_communities": main_communities,
        "subcommunities": {}
    }
    
    for community in main_communities:
        community_id = community["id"]
        subcommunities = retrieve_subcommunities(
            community_id=community_id,
            depth=subcommunity_depth,
            limit=subcommunity_limit
        )
        result["subcommunities"][community_id] = subcommunities
    
    return result


def get_neo4j_tools():
    return [
        retrieve_communities_by_property,
        retrieve_communities_by_embedding,
        retrieve_subcommunities,
        retrieve_community_then_subcommunities,
    ]
