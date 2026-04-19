import networkx as nx
from database import get_all_nodes, get_all_prereqs_map, get_nexts
from typing import List, Dict, Optional

def build_graph() -> nx.DiGraph:
    """
    构建知识图谱有向图

    Returns:
        networkx.DiGraph: 包含所有知识点和前置关系的有向图，节点属性包含name和difficulty
    """
    # 获取所有节点数据
    nodes = get_all_nodes()
    prereqs_map = get_all_prereqs_map()

    # 创建有向图
    G = nx.DiGraph()

    # 添加节点及其属性
    for node in nodes:
        G.add_node(
            node['id'],
            name=node['name'],
            difficulty=node['difficulty']
        )

    # 添加边（前置关系）
    for to_id, from_ids in prereqs_map.items():
        for from_id in from_ids:
            G.add_edge(from_id, to_id)

    return G

def recommend_next(learned_ids: List[int], strategy: str = 'difficulty') -> Optional[int]:
    """
    基于知识图谱推荐下一个学习知识点

    Args:
        learned_ids: 已学知识点ID列表
        strategy: 推荐策略，'difficulty'按难度升序，'core'按核心程度降序

    Returns:
        推荐的知识点ID，若无候选则返回None
    """
    # 构建知识图谱
    G = build_graph()

    # 获取所有节点
    all_nodes = get_all_nodes()

    # 筛选候选节点：未学习且所有前置知识点都已掌握
    candidates = []
    learned_set = set(learned_ids)  # 转换为集合以提高查找效率

    for node in all_nodes:
        node_id = node['id']

        # 跳过已学节点
        if node_id in learned_set:
            continue

        # 检查所有前置知识点是否都已学习
        prerequisites = get_prerequisites_for_node(node_id)
        if all(pre_req in learned_set for pre_req in prerequisites):
            candidates.append(node_id)

    # 如果没有候选节点，返回None
    if not candidates:
        return None

    # 根据策略对候选节点排序并返回最佳推荐
    if strategy == 'core':
        # 按核心程度排序：出度（后置数量）降序
        candidates.sort(key=lambda x: len(get_nexts(x)), reverse=True)
    else:
        # 默认按难度升序排序
        candidates.sort(key=lambda x: get_node_difficulty(x))

    return candidates[0]

def get_prerequisites_for_node(node_id: int) -> List[int]:
    """
    获取指定节点的所有前置知识点ID列表

    Args:
        node_id: 目标节点ID

    Returns:
        前置知识点ID列表
    """
    try:
        prereqs_map = get_all_prereqs_map()
        return prereqs_map.get(node_id, [])
    except Exception as e:
        print(f"获取前置知识点失败: {e}")
        return []

def get_node_difficulty(node_id: int) -> int:
    """
    获取指定节点的难度值

    Args:
        node_id: 节点ID

    Returns:
        难度值，如果节点不存在则返回最大整数
    """
    try:
        node = next((n for n in get_all_nodes() if n['id'] == node_id), None)
        return node['difficulty'] if node else float('inf')
    except Exception as e:
        print(f"获取节点难度失败: {e}")
        return float('inf')
