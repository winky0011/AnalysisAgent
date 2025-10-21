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