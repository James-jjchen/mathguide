import networkx as nx
import database
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

def get_weakest_nodes(user_id: str, threshold: float = 0.5, limit: int = 5) -> list:
    """
    获取用户掌握度最低的知识点列表

    Args:
        user_id: 用户ID
        threshold: 低于此掌握度视为薄弱，默认0.5
        limit: 最多返回数量

    Returns:
        [{"node_id": int, "name": str, "mastery": float, "priority": str}, ...]
        按掌握度升序排列
    """
    mastery = database.get_all_user_mastery(user_id)
    weak = [(nid, m) for nid, m in mastery.items() if m < threshold]
    weak.sort(key=lambda x: x[1])

    result = []
    for node_id, m in weak[:limit]:
        node = database.get_node(node_id)
        if node:
            if m < 0.2:
                priority = "high"
            elif m < 0.35:
                priority = "medium"
            else:
                priority = "low"
            result.append({
                "node_id": node_id,
                "name": node["name"],
                "mastery": round(m, 2),
                "priority": priority
            })
    return result


def compute_knowledge_layers() -> Dict[int, int]:
    """
    使用拓扑排序和最长路径算法计算每个知识点的层级。

    层级0 = 无前置知识点的根节点
    层级N = max(所有前置节点层级) + 1

    Returns:
        {node_id: layer_index}
    """
    G = build_graph()
    topo_order = list(nx.topological_sort(G))
    layers: Dict[int, int] = {}
    for node_id in topo_order:
        predecessors = list(G.predecessors(node_id))
        if not predecessors:
            layers[node_id] = 0
        else:
            layers[node_id] = max(layers[p] for p in predecessors) + 1
    return layers


def compute_stage_map(user_id: str) -> tuple:
    """
    计算用户的闯关地图：每个节点的层级、状态和掌握度。

    状态规则：
    - cleared:  mastery >= 0.7
    - unlocked: 未cleared，但所有前置节点均已cleared
    - locked:   未cleared，且至少一个前置节点未cleared

    Args:
        user_id: 用户ID

    Returns:
        (layers_list, prerequisites_list, summary_dict)
        layers_list = [{"layer": 0, "nodes": [...]}, ...]
    """
    CLEAR_THRESHOLD = 0.7

    layers_map = compute_knowledge_layers()
    mastery_map = database.get_all_user_mastery(user_id)
    prereqs_map = database.get_all_prereqs_map()
    all_nodes = database.get_all_nodes()

    # Iterate in topological order so prerequisites are processed before dependents
    topo_order = sorted(all_nodes, key=lambda n: layers_map.get(n['id'], 0))

    # Determine status for each node
    statuses = {}
    for node in topo_order:
        nid = node['id']
        m = mastery_map.get(nid, 0.0)
        if m >= CLEAR_THRESHOLD:
            statuses[nid] = 'cleared'
        else:
            prereq_ids = prereqs_map.get(nid, [])
            all_cleared = all(statuses.get(pid) == 'cleared' for pid in prereq_ids)
            statuses[nid] = 'unlocked' if all_cleared else 'locked'

    # Group nodes by layer
    max_layer = max(layers_map.values()) if layers_map else 0
    layers_list = []
    for layer_idx in range(max_layer + 1):
        layer_nodes = []
        for node in all_nodes:
            nid = node['id']
            if layers_map.get(nid) == layer_idx:
                layer_nodes.append({
                    'node_id': nid,
                    'name': node['name'],
                    'difficulty': node['difficulty'],
                    'chapter_id': node['chapter_id'],
                    'status': statuses[nid],
                    'mastery': round(mastery_map.get(nid, 0.0), 2),
                })
        # Sort within layer by difficulty
        layer_nodes.sort(key=lambda x: x['difficulty'])
        layers_list.append({'layer': layer_idx, 'nodes': layer_nodes})

    # Build prerequisites edge list
    prerequisites_list = []
    for to_id, from_ids in prereqs_map.items():
        for from_id in from_ids:
            prerequisites_list.append({'from': from_id, 'to': to_id})

    # Build summary
    cleared_count = sum(1 for s in statuses.values() if s == 'cleared')
    unlocked_count = sum(1 for s in statuses.values() if s == 'unlocked')
    locked_count = sum(1 for s in statuses.values() if s == 'locked')

    summary = {
        'total': len(all_nodes),
        'cleared': cleared_count,
        'unlocked': unlocked_count,
        'locked': locked_count,
    }

    return layers_list, prerequisites_list, summary


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
