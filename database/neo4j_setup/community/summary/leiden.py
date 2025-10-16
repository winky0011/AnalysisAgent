from typing import List, Dict
from .base import BaseSummarizer
import time

from settings import BATCH_SIZE

class LeidenSummarizer(BaseSummarizer):
    """Leiden算法的社区摘要生成器"""
    
    def collect_community_info(self) -> List[Dict]:
        """收集Leiden社区信息"""
        start_time = time.time()
        print("收集Leiden社区信息...")
        
        try:
            # 获取社区总数
            count_result = self.graph.query("""
            MATCH (c:`__Community__` {level: 0})
            RETURN count(c) AS community_count
            """)
            
            community_count = count_result[0]['community_count'] if count_result else 0
            if not community_count:
                print("没有找到Leiden社区")
                return []
                
            print(f"找到 {community_count} 个Leiden社区，开始收集详细信息")
            
            if community_count > 1000:
                return self._collect_info_in_batches(community_count)
            
            # 收集所有社区信息
            result = self.graph.query("""
            // 找到最底层(level=0)的社区
            MATCH (c:`__Community__` {level: 0})
            // 优先处理有较高排名的社区
            WITH c ORDER BY CASE WHEN c.community_rank IS NULL 
                            THEN 0 ELSE c.community_rank END DESC
            LIMIT 200
            
            // 获取社区中的实体
            MATCH (c)<-[:IN_COMMUNITY]-(e:__Entity__)
            WITH c, collect(e) as nodes
            WHERE size(nodes) > 1
            
            // 获取实体间的关系
            CALL {
                WITH nodes
                MATCH (n1:__Entity__)
                WHERE n1 IN nodes
                MATCH (n2:__Entity__)
                WHERE n2 IN nodes AND id(n1) < id(n2)
                MATCH (n1)-[r]->(n2)
                RETURN collect(distinct r) as relationships
            }
            
            // 返回格式化的结果
            RETURN c.id AS communityId,
                [n in nodes | {
                    id: n.id, 
                    description: n.description, 
                    type: CASE WHEN size([el in labels(n) WHERE el <> '__Entity__']) > 0 
                            THEN [el in labels(n) WHERE el <> '__Entity__'][0] 
                            ELSE 'Unknown' END
                }] AS nodes,
                [r in relationships | {
                    start: startNode(r).id, 
                    type: type(r), 
                    end: endNode(r).id, 
                    description: r.description
                }] AS rels
            """)
            
            elapsed_time = time.time() - start_time
            print(f"收集到 {len(result)} 个Leiden社区信息，耗时: {elapsed_time:.2f}秒")
            return result
            
        except Exception as e:
            print(f"收集Leiden社区信息失败: {e}")
            return self._collect_info_fallback()
    
    def _collect_info_in_batches(self, total_count: int) -> List[Dict]:
        """分批收集社区信息"""
        batch_size = 50  # 默认批处理大小
        if BATCH_SIZE:
            batch_size = min(50, max(10, BATCH_SIZE // 2))  # 调整为适合社区收集的批次大小
            
        total_batches = (total_count + batch_size - 1) // batch_size
        all_results = []
        
        print(f"使用批处理收集Leiden社区信息，共 {total_batches} 批")
        
        for batch in range(total_batches):
            if batch > 20:  # 限制批次
                print("已达到最大批次限制(20)，停止收集")
                break
                
            skip = batch * batch_size
            
            try:
                batch_result = self.graph.query("""
                // 分批获取社区
                MATCH (c:`__Community__`)
                WHERE c.level = 0
                WITH c ORDER BY CASE WHEN c.community_rank IS NULL 
                            THEN 0 ELSE c.community_rank END DESC
                SKIP $skip LIMIT $batch_size
                
                // 获取社区实体
                MATCH (c)<-[:IN_COMMUNITY]-(e:__Entity__)
                WITH c, collect(e) as nodes
                WHERE size(nodes) > 1
                
                // 获取实体间关系
                CALL {
                    WITH nodes
                    MATCH (n1:__Entity__)
                    WHERE n1 IN nodes
                    MATCH (n2:__Entity__)
                    WHERE n2 IN nodes AND id(n1) < id(n2)
                    MATCH (n1)-[r]->(n2)
                    WITH collect(distinct r) as relationships
                    LIMIT 100
                    RETURN relationships
                }
                
                // 格式化返回结果
                RETURN c.id AS communityId,
                    [n in nodes | {
                        id: n.id, 
                        description: n.description, 
                        type: CASE WHEN size([el in labels(n) WHERE el <> '__Entity__']) > 0 
                                THEN [el in labels(n) WHERE el <> '__Entity__'][0] 
                                ELSE 'Unknown' END
                    }] AS nodes,
                    [r in relationships | {
                        start: startNode(r).id, 
                        type: type(r), 
                        end: endNode(r).id, 
                        description: r.description
                    }] AS rels
                """, params={"skip": skip, "batch_size": batch_size})
                
                all_results.extend(batch_result)
                print(f"批次 {batch+1}/{total_batches} 完成，收集到 {len(batch_result)} 个社区")
                
            except Exception as e:
                print(f"批次 {batch+1} 处理出错: {e}")
                continue
        
        return all_results
    
    def _collect_info_fallback(self) -> List[Dict]:
        """备用的信息收集方法"""
        try:
            print("尝试使用简化查询收集社区信息...")
            result = self.graph.query("""
            // 使用简化的查询获取基本信息
            MATCH (c:`__Community__` {level: 0})
            WITH c LIMIT 50
            MATCH (c)<-[:IN_COMMUNITY]-(e:__Entity__)
            WITH c, collect(e) as nodes
            WHERE size(nodes) > 1
            RETURN c.id AS communityId,
                [n in nodes | {
                    id: n.id, 
                    description: coalesce(n.description, 'No description'), 
                    type: CASE WHEN size(labels(n)) > 0 THEN labels(n)[0] ELSE 'Unknown' END
                }] AS nodes,
                [] AS rels  // 简化版本不包含关系信息
            """)
            
            print(f"使用简化查询收集到 {len(result)} 个社区信息")
            return result
        except Exception as e:
            print(f"简化查询也失败: {e}")
            return []