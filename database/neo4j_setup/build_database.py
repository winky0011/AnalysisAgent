import sys
import os
import argparse

def setup_path():
    """
    设置模块导入路径。
    将项目根目录和 build 目录添加到 sys.path，以确保所有模块都能被正确找到。
    """
    # 获取当前脚本所在目录 (database/neo4j_setup)
    neo4j_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 项目根目录
    project_root = os.path.dirname(neo4j_dir)
    
    # build 目录
    build_dir = os.path.join(neo4j_dir, 'build')

    # 添加到 sys.path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if build_dir not in sys.path:
        sys.path.insert(0, build_dir)

def main():
    """
    脚本主函数。
    """
    setup_path()
    
    parser = argparse.ArgumentParser(description="Neo4j 数据库构建工具。")
    parser.add_argument(
        '--build',
        action='store_true',
        help='执行完整的知识图谱构建流程。'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='执行增量更新流程。'
    )

    # # 运行增量更新（单次）
    # python -m build.incremental_update --once

    args = parser.parse_args()

    if args.build:
        from build.main import KnowledgeGraphProcessor

        print("开始知识图谱构建流程...")
        try:
            processor = KnowledgeGraphProcessor()
            processor.process_all()
            print("知识图谱构建流程成功完成。")
        except Exception as e:
            print(f"数据库构建过程中发生错误: {e}")
            import traceback
            traceback.print_exc()

    elif args.incremental:
        from build.incremental_update import IncrementalUpdateManager
        print("开始增量更新流程...")
        try:
            manager = IncrementalUpdateManager()
            manager.run_once()
            print("增量更新流程成功完成。")
        except Exception as e:
            print(f"增量更新过程中发生错误: {e}")
            import traceback
            traceback.print_exc()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()