# 数据库管理

本目录包含了项目所需数据库的初始化、构建和数据填充脚本。目前支持 **MySQL** 和 **Neo4j** 两种数据库。

neo4j的代码源于：https://github.com/1517005260/graph-rag-agent

## 目录结构
```
database/
├── mysql/
│   └── gen_data.py        # MySQL数据库表创建和测试数据填充脚本
├── neo4j/
│   ├── build/             # Neo4j图谱构建的核心逻辑
│   ├── community/         # build的工具模块，社区检测与摘要模块
│   ├── graph/             # build的工具模块，图谱构建模块
│   ├── files/             # 用于构建知识图谱的源文件
│   ├── processing/        # 文件处理
│   └── build_database.py  # Neo4j知识图谱构建的入口脚本
```

## 1. MySQL 数据库

`mysql` 目录下的脚本用于初始化关系型数据库，包括创建表结构和填充初始的测试数据。

### 使用方法

#### a. 环境配置

在运行脚本前，请确保项目根目录下的 `.env` 文件已创建，并包含以下 MySQL 连接信息：

```env
MYSQL_HOST=your_mysql_host
MYSQL_USER=your_mysql_username
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=your_database_name
```

#### b. 安装依赖

脚本依赖 `Faker` 库来生成测试数据。请通过以下命令安装：

```bash
pip install Faker mysql-connector-python
```

#### c. 执行脚本

进入 `mysql` 目录，并运行 `seed_database.py` 脚本来创建表和填充数据：

```bash
cd database/mysql
python seed_database.py --seed
```

如果是通过uv管理环境，需要先激活环境，再运行脚本：

```bash
.venv\Scripts\activate.bat
uv run python database/mysql/seed_database.py --seed
```

脚本将自动创建 `users` 和 `documents` 表，并向其中填充模拟数据。


## 2. Neo4j 知识图谱

`neo4j` 目录下的脚本用于构建知识图谱。它会读取 `neo4j/files/` 目录下的文档，提取实体和关系，并将其存入 Neo4j 数据库。

### 使用方法

#### a. 环境配置

请确保项目根目录下的 `.env` 文件中已配置 Neo4j 的连接凭据：

```env
NEO4J_URI=bolt://your_neo4j_host:7687
NEO4J_USERNAME=your_neo4j_username
NEO4J_PASSWORD=your_neo4j_password
```

#### b. 执行脚本

进入 `neo4j` 目录，并运行 `build_database.py` 脚本来启动完整的图谱构建流程：

```bash
cd database/neo4j
python build_database.py --build
```

```bash
.venv\Scripts\activate.bat
uv run python database/neo4j_setup/build_database.py --build
```

该过程可能需要一些时间，具体取决于源文件的大小和复杂性。


## 注意事项

- 在执行任何数据库脚本之前，请确保目标数据库服务正在运行。
- 脚本被设计为可重复执行。例如，如果表已存在，`seed_database.py` 不会尝试重新创建它们。