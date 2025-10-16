from pathlib import Path

# ===== 基础配置 =====

# 基础路径设置
BASE_DIR = Path(__file__).resolve().parent.parent
FILES_DIR = BASE_DIR / 'database/neo4j_setup/files'

# 知识库主题设置，用于deepsearch（reasoning提示词）
KB_NAME = "项目管理"

# 系统运行参数
workers = 2  # fastapi 并发进程数

# ===== 知识图谱配置 =====

# 知识图谱主题设置
theme = "学生管理"

# 知识图谱实体与关系类型
entity_types = [
    "学生类型",
    "奖学金类型",
    "处分类型",
    "部门",
    "学生职责",
    "管理规定"
]

relationship_types = [
    "申请",
    "评选",
    "违纪",
    "资助",
    "申诉",
    "管理",
    "权利义务",
    "互斥",
]

# 冲突解决与更新策略
# manual_first: 优先保留手动编辑
# auto_first: 优先自动更新
# merge: 尝试合并
conflict_strategy = "manual_first"

# 社区检测算法配置
# sllpa如果发现不了社区，则换成leiden效果会好一点
community_algorithm = 'leiden'

# ===== 文本处理配置 =====

# 文本处理参数
CHUNK_SIZE = 500
OVERLAP = 100
MAX_TEXT_LENGTH = 500000
similarity_threshold = 0.9

# 回答生成配置
response_type = "多个段落"

# ===== 性能优化配置 =====

# 并行处理配置
MAX_WORKERS = 4                # 并行工作线程数
BATCH_SIZE = 100               # 批处理大小
ENTITY_BATCH_SIZE = 50         # 实体处理批次大小
CHUNK_BATCH_SIZE = 100         # 文本块处理批次大小
EMBEDDING_BATCH_SIZE = 64      # 嵌入向量计算批次大小
LLM_BATCH_SIZE = 5             # LLM处理批次大小

# 索引和社区检测配置
COMMUNITY_BATCH_SIZE = 50      # 社区处理批次大小

# GDS相关配置
GDS_MEMORY_LIMIT = 6           # GDS内存限制(GB)
GDS_CONCURRENCY = 4            # GDS并发度
GDS_NODE_COUNT_LIMIT = 50000   # GDS节点数量限制
GDS_TIMEOUT_SECONDS = 300      # GDS超时时间(秒)

# ===== 搜索模块配置 =====

# 本地搜索配置
LOCAL_SEARCH_CONFIG = {
    # 向量检索参数
    "top_entities": 10,
    "top_chunks": 10,
    "top_communities": 2,
    "top_outside_rels": 10,
    "top_inside_rels": 10,

    # 索引配置
    "index_name": "vector",
    "response_type": response_type,

    # 检索查询模板
    "retrieval_query": """
    WITH collect(node) as nodes
    WITH
    collect {
        UNWIND nodes as n
        MATCH (n)<-[:MENTIONS]-(c:__Chunk__)
        WITH distinct c, count(distinct n) as freq
        RETURN {id:c.id, text: c.text} AS chunkText
        ORDER BY freq DESC
        LIMIT $topChunks
    } AS text_mapping,
    collect {
        UNWIND nodes as n
        MATCH (n)-[:IN_COMMUNITY]->(c:__Community__)
        WITH distinct c, c.community_rank as rank, c.weight AS weight
        RETURN c.summary
        ORDER BY rank, weight DESC
        LIMIT $topCommunities
    } AS report_mapping,
    collect {
        UNWIND nodes as n
        MATCH (n)-[r]-(m:__Entity__)
        WHERE NOT m IN nodes
        RETURN r.description AS descriptionText
        ORDER BY r.weight DESC
        LIMIT $topOutsideRels
    } as outsideRels,
    collect {
        UNWIND nodes as n
        MATCH (n)-[r]-(m:__Entity__)
        WHERE m IN nodes
        RETURN r.description AS descriptionText
        ORDER BY r.weight DESC
        LIMIT $topInsideRels
    } as insideRels,
    collect {
        UNWIND nodes as n
        RETURN n.description AS descriptionText
    } as entities
    RETURN {
        Chunks: text_mapping,
        Reports: report_mapping,
        Relationships: outsideRels + insideRels,
        Entities: entities
    } AS text, 1.0 AS score, {} AS metadata
    """,
}

# 全局搜索配置
GLOBAL_SEARCH_CONFIG = {
    # 社区层级配置
    "default_level": 0,  # 层级0
    "response_type": response_type,

    # 批处理配置
    "batch_size": 10,
    "max_communities": 100,
}

# ===== 缓存配置 =====

# 搜索缓存配置
SEARCH_CACHE_CONFIG = {
    # 缓存目录
    "base_cache_dir": "./cache",
    "local_search_cache_dir": "./cache/local_search",
    "global_search_cache_dir": "./cache/global_search",
    "deep_research_cache_dir": "./cache/deep_research",

    # 缓存策略
    "max_cache_size": 200,
    "cache_ttl": 3600,  # 1小时

    # 内存缓存配置
    "memory_cache_enabled": True,
    "disk_cache_enabled": True,
}

# ===== 推理配置 =====

# 推理引擎配置
REASONING_CONFIG = {
    # 迭代配置
    "max_iterations": 5,
    "max_search_limit": 10,

    # 思考引擎配置
    "thinking_depth": 3,
    "exploration_width": 3,
    "max_exploration_steps": 5,

    # 证据链配置
    "max_evidence_items": 50,
    "evidence_relevance_threshold": 0.7,

    # 验证配置
    "validation": {
        "enable_answer_validation": True,
        "validation_threshold": 0.8,
        "enable_complexity_estimation": True,
        "consistency_threshold": 0.7
    },

    # 探索配置
    "exploration": {
        "max_exploration_steps": 5,
        "exploration_depth": 3,
        "exploration_breadth": 3,
        "exploration_width": 3,
        "relevance_threshold": 0.5,
        "exploration_decay_factor": 0.8,
        "enable_backtracking": True
    }
}