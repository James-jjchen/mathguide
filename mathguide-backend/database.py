import sqlite3
import csv
import os
import json
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional

# 数据库文件路径
DATABASE = 'instance\mathguide.db'


def init_db():
    """
    初始化数据库，创建表并导入CSV数据
    如果数据库文件已存在，则跳过初始化
    """
    if os.path.exists(DATABASE):
        print(f"数据库文件 {DATABASE} 已存在，跳过初始化")
        return

    # 确保instance目录存在
    os.makedirs('instance', exist_ok=True)

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # 创建knowledge_nodes表（添加chapter_id字段）
        cursor.execute('''
                       CREATE TABLE knowledge_nodes
                       (
                           id         INTEGER PRIMARY KEY,
                           name       TEXT    NOT NULL,
                           difficulty INTEGER NOT NULL,
                           chapter_id INTEGER
                       )
                       ''')

        # 创建prerequisites表（使用联合主键）
        cursor.execute('''
                       CREATE TABLE prerequisites
                       (
                           from_id INTEGER NOT NULL,
                           to_id   INTEGER NOT NULL,
                           PRIMARY KEY (from_id, to_id)
                       )
                       ''')

        # 创建user_mastery表：记录每个用户对每个知识点的掌握度
        cursor.execute('''
                       CREATE TABLE user_mastery
                       (
                           user_id      TEXT    NOT NULL,
                           node_id      INTEGER NOT NULL,
                           mastery      REAL    NOT NULL DEFAULT 0.0 CHECK (mastery >= 0 AND mastery <= 1.0),
                           last_updated TIMESTAMP        DEFAULT CURRENT_TIMESTAMP,
                           PRIMARY KEY (user_id, node_id),
                           FOREIGN KEY (node_id) REFERENCES knowledge_nodes (id)
                       )
                       ''')

        # 创建practice_sessions表：记录每次练习的完整数据
        cursor.execute('''
                       CREATE TABLE practice_sessions
                       (
                           id              INTEGER PRIMARY KEY AUTOINCREMENT,
                           user_id         TEXT    NOT NULL,
                           target_nodes    TEXT    NOT NULL,
                           questions_json  TEXT    NOT NULL,
                           results_json    TEXT    NOT NULL,
                           average_score   REAL    NOT NULL DEFAULT 0.0,
                           total_questions INTEGER NOT NULL DEFAULT 0,
                           created_at      TIMESTAMP        DEFAULT CURRENT_TIMESTAMP
                       )
                       ''')

        # 从CSV文件导入knowledge_nodes数据
        with open('data\knowledge_nodes.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 根据知识点ID分配章节ID（可根据实际情况调整）
                node_id = int(row['id'])
                if node_id <= 8:
                    chapter_id = 1  # 函数与极限
                elif node_id <= 15:
                    chapter_id = 2  # 导数与微分
                elif node_id <= 23:
                    chapter_id = 3  # 积分学
                else:
                    chapter_id = None

                cursor.execute(
                    'INSERT INTO knowledge_nodes (id, name, difficulty, chapter_id) VALUES (?, ?, ?, ?)',
                    (node_id, row['name'], int(row['difficulty']), chapter_id)
                )

        # 从CSV文件导入prerequisites数据
        with open('data\prerequisites.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    'INSERT INTO prerequisites (from_id, to_id) VALUES (?, ?)',
                    (int(row['from_id']), int(row['to_id']))
                )

        conn.commit()
        print("数据库初始化完成")

    except FileNotFoundError as e:
        print(f"文件未找到: {e}")
        raise
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def ensure_practice_sessions_table():
    """确保 practice_sessions 表存在（用于已有数据库的迁移）"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS practice_sessions
            (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         TEXT    NOT NULL,
                target_nodes    TEXT    NOT NULL,
                questions_json  TEXT    NOT NULL,
                results_json    TEXT    NOT NULL,
                average_score   REAL    NOT NULL DEFAULT 0.0,
                total_questions INTEGER NOT NULL DEFAULT 0,
                created_at      TIMESTAMP        DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"创建 practice_sessions 表失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def _fuzzy_match_node(skill_graph_node_name: str, db_nodes: Dict[str, int]) -> Optional[int]:
    """Match a skill_graph node name to the closest knowledge_nodes id."""
    # Direct match
    if skill_graph_node_name in db_nodes:
        return db_nodes[skill_graph_node_name]
    # Try stripping parenthetical suffixes from DB names for matching
    for db_name, nid in db_nodes.items():
        base = db_name.split("（")[0].split("(")[0].strip()
        if skill_graph_node_name == base:
            return nid
    # Fuzzy match
    best_ratio, best_id = 0.0, None
    for db_name, nid in db_nodes.items():
        ratio = SequenceMatcher(None, skill_graph_node_name, db_name).ratio()
        if ratio > best_ratio:
            best_ratio, best_id = ratio, nid
    if best_ratio >= 0.3:
        return best_id
    return None


def ensure_skill_dimensions_table():
    """Create skill_dimensions table if it does not exist."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skill_dimensions (
                dim_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_node_id INTEGER NOT NULL,
                difficulty INTEGER NOT NULL DEFAULT 1,
                node_weight REAL NOT NULL DEFAULT 1.0,
                FOREIGN KEY (parent_node_id) REFERENCES knowledge_nodes(id)
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"创建 skill_dimensions 表失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def ensure_skill_edges_table():
    """Create skill_edges table if it does not exist."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skill_edges (
                from_dim TEXT NOT NULL,
                to_dim TEXT NOT NULL,
                transfer_gain REAL NOT NULL DEFAULT 0.0,
                cognitive_distance INTEGER NOT NULL DEFAULT 3,
                edge_type TEXT NOT NULL DEFAULT 'transfer',
                PRIMARY KEY (from_dim, to_dim)
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"创建 skill_edges 表失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def ensure_user_dim_params_table():
    """Create user_dim_params table if it does not exist."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_dim_params (
                user_id TEXT NOT NULL,
                dim_id TEXT NOT NULL,
                alpha REAL NOT NULL DEFAULT 1.0,
                beta REAL NOT NULL DEFAULT 1.0,
                stuck_count INTEGER NOT NULL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, dim_id),
                FOREIGN KEY (dim_id) REFERENCES skill_dimensions(dim_id)
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"创建 user_dim_params 表失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def migrate_skill_dimensions():
    """Parse skill_graph.json and populate skill_dimensions + skill_edges tables.
    Safe to call multiple times — skips if skill_dimensions already has data."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Check if migration already done
        cursor.execute('SELECT COUNT(*) FROM skill_dimensions')
        if cursor.fetchone()[0] > 0:
            print("skill_dimensions 已有数据，跳过迁移")
            conn.close()
            return

        # Load skill_graph.json
        graph_path = os.path.join('data', 'skill_graph.json')
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)

        # Build DB node name → id mapping
        cursor.execute('SELECT id, name FROM knowledge_nodes')
        db_nodes = {row[1]: row[0] for row in cursor.fetchall()}

        # Map skill_graph string node_id → knowledge_nodes integer id
        sg_node_to_db: Dict[str, int] = {}
        for sg_nid, sg_node in graph.get('nodes', {}).items():
            matched = _fuzzy_match_node(sg_node['name'], db_nodes)
            if matched is not None:
                sg_node_to_db[sg_nid] = matched
            else:
                # Default to first node in the same chapter
                ch = sg_node.get('chapter_id', 'ch1')
                ch_map = {'ch1': 1, 'ch2': 9, 'ch3': 16}
                sg_node_to_db[sg_nid] = ch_map.get(ch, 1)

        # Insert dimensions
        dims = graph.get('dimensions', {})
        for dim_id, dim_info in dims.items():
            parent_sg_nid = dim_info.get('parent_node', dim_info.get('parent_node_id', ''))
            parent_db_id = sg_node_to_db.get(parent_sg_nid, 1)
            cursor.execute(
                '''INSERT OR IGNORE INTO skill_dimensions
                   (dim_id, name, parent_node_id, difficulty, node_weight)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    dim_id,
                    dim_info.get('name', dim_id),
                    parent_db_id,
                    dim_info.get('difficulty', 1),
                    dim_info.get('node_weight', 1.0),
                )
            )

        # Insert edges from skill_graph.json edges array
        for edge in graph.get('edges', []):
            cursor.execute(
                '''INSERT OR IGNORE INTO skill_edges
                   (from_dim, to_dim, transfer_gain, cognitive_distance, edge_type)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    edge['from_dim'],
                    edge['to_dim'],
                    edge.get('transfer_gain', 0.0),
                    edge.get('cognitive_distance', 3),
                    edge.get('edge_type', 'transfer'),
                )
            )

        # Generate sibling edges: dimensions in the same node get transfer_gain=0.3
        for sg_nid, sg_node in graph.get('nodes', {}).items():
            node_dims = sg_node.get('dimensions', [])
            for i, da in enumerate(node_dims):
                for db in node_dims[i + 1:]:
                    cursor.execute(
                        '''INSERT OR IGNORE INTO skill_edges
                           (from_dim, to_dim, transfer_gain, cognitive_distance, edge_type)
                           VALUES (?, ?, 0.3, 1, 'sibling')''',
                        (da, db)
                    )
                    cursor.execute(
                        '''INSERT OR IGNORE INTO skill_edges
                           (from_dim, to_dim, transfer_gain, cognitive_distance, edge_type)
                           VALUES (?, ?, 0.3, 1, 'sibling')''',
                        (db, da)
                    )

        conn.commit()
        print(f"skill_dimensions 迁移完成: {len(dims)} 个维度, {len(graph.get('edges', []))} 条边")
    except Exception as e:
        print(f"技能维度迁移失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def migrate_user_dim_params():
    """Migrate existing user_mastery data to user_dim_params.
    Distributing node mastery evenly across its dimensions."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Check if user_dim_params already has data
        cursor.execute('SELECT COUNT(*) FROM user_dim_params')
        if cursor.fetchone()[0] > 0:
            print("user_dim_params 已有数据，跳过迁移")
            conn.close()
            return

        # Load skill_graph for dimension info
        graph_path = os.path.join('data', 'skill_graph.json')
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)

        # Build a map: knowledge_node id → list of dim_ids
        cursor.execute('SELECT dim_id, parent_node_id FROM skill_dimensions')
        node_dim_map: Dict[int, List[str]] = {}
        for row in cursor.fetchall():
            dim_id, parent_node_id = row[0], row[1]
            node_dim_map.setdefault(parent_node_id, []).append(dim_id)

        # For each user, get their mastery and distribute to dims
        cursor.execute('SELECT DISTINCT user_id FROM user_mastery')
        users = [row[0] for row in cursor.fetchall()]

        migrated = 0
        for user_id in users:
            cursor.execute(
                'SELECT node_id, mastery FROM user_mastery WHERE user_id = ?',
                (user_id,)
            )
            for node_id, mastery in cursor.fetchall():
                dims = node_dim_map.get(node_id, [])
                if not dims:
                    continue
                # Distribute node mastery evenly: alpha = mastery * 10 + 1, beta = (1-mastery) * 10 + 1
                alpha = max(0.1, mastery * 10.0 + 1.0)
                beta_val = max(0.1, (1.0 - mastery) * 10.0 + 1.0)
                for dim_id in dims:
                    cursor.execute(
                        '''INSERT OR IGNORE INTO user_dim_params
                           (user_id, dim_id, alpha, beta, stuck_count)
                           VALUES (?, ?, ?, ?, 0)''',
                        (user_id, dim_id, alpha, beta_val)
                    )
                migrated += 1

        conn.commit()
        print(f"user_dim_params 迁移完成: {migrated} 条节点记录")
    except Exception as e:
        print(f"用户维度参数迁移失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def run_all_migrations():
    """Run all dimension-level migrations. Safe to call multiple times."""
    ensure_skill_dimensions_table()
    ensure_skill_edges_table()
    ensure_user_dim_params_table()
    ensure_user_meta_table()
    migrate_skill_dimensions()
    migrate_user_dim_params()


def save_practice_session(user_id: str, target_nodes: List[int], questions: List[Dict],
                          results_data: Dict) -> int:
    """保存一次练习记录，返回记录ID"""
    import json
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO practice_sessions
               (user_id, target_nodes, questions_json, results_json, average_score, total_questions)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                json.dumps(target_nodes, ensure_ascii=False),
                json.dumps(questions, ensure_ascii=False),
                json.dumps(results_data, ensure_ascii=False),
                results_data.get('summary', {}).get('average_score', 0),
                results_data.get('summary', {}).get('total', 0),
            )
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"保存练习记录失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_practice_history(user_id: str, limit: int = 20) -> List[Dict]:
    """获取用户的练习历史记录"""
    import json
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT id, user_id, target_nodes, questions_json, results_json,
                      average_score, total_questions, created_at
               FROM practice_sessions
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?''',
            (user_id, limit)
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d['target_nodes'] = json.loads(d['target_nodes'])
            d['questions'] = json.loads(d['questions_json'])
            d['results'] = json.loads(d['results_json'])
            del d['questions_json']
            del d['results_json']
            result.append(d)
        return result
    except Exception as e:
        print(f"查询练习历史失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_all_nodes() -> List[Dict]:
    """
    获取所有知识节点

    Returns:
        包含所有知识节点的列表，每个节点为字典形式
    """
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM knowledge_nodes ORDER BY id')
        rows = cursor.fetchall()

        # 将Row对象转换为字典
        result = [dict(row) for row in rows]
        return result

    except Exception as e:
        print(f"查询所有节点失败: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_node(node_id: int) -> Optional[Dict]:
    """
    根据ID获取单个知识节点

    Args:
        node_id: 知识节点ID

    Returns:
        节点字典，如果不存在则返回None
    """
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM knowledge_nodes WHERE id = ?', (node_id,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    except Exception as e:
        print(f"查询节点失败: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_prerequisites(to_id: int) -> List[Dict]:
    """
    获取指定节点的所有前置知识点

    Args:
        to_id: 目标节点ID

    Returns:
        前置知识点列表
    """
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 使用JOIN查询获取完整的前置节点信息
        cursor.execute('''
            SELECT kn.* FROM knowledge_nodes kn
            JOIN prerequisites p ON kn.id = p.from_id
            WHERE p.to_id = ?
            ORDER BY kn.id
        ''', (to_id,))

        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        return result

    except Exception as e:
        print(f"查询前置知识点失败: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_nexts(from_id: int) -> List[Dict]:
    """
    获取指定节点的所有后续知识点

    Args:
        from_id: 源节点ID

    Returns:
        后续知识点列表
    """
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 使用JOIN查询获取完整的后续节点信息
        cursor.execute('''
            SELECT kn.* FROM knowledge_nodes kn
            JOIN prerequisites p ON kn.id = p.to_id
            WHERE p.from_id = ?
            ORDER BY kn.id
        ''', (from_id,))

        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        return result

    except Exception as e:
        print(f"查询后续知识点失败: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_all_prereqs_map() -> Dict[int, List[int]]:
    """
    获取所有前置关系的映射表

    Returns:
        字典，键为目标节点ID，值为前置节点ID列表
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('SELECT from_id, to_id FROM prerequisites ORDER BY to_id, from_id')
        rows = cursor.fetchall()

        # 构建映射表
        prereqs_map = {}
        for from_id, to_id in rows:
            if to_id not in prereqs_map:
                prereqs_map[to_id] = []
            prereqs_map[to_id].append(from_id)

        return prereqs_map

    except Exception as e:
        print(f"获取前置关系映射表失败: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_user_mastery(user_id: str):
    """
    初始化用户掌握度表，将所有知识点掌握度设为0

    Args:
        user_id: 用户ID
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # 获取所有知识点ID
        cursor.execute('SELECT id FROM knowledge_nodes')
        nodes = cursor.fetchall()

        # 插入初始掌握度（全部为0）
        for (node_id,) in nodes:
            cursor.execute(
                'INSERT OR IGNORE INTO user_mastery (user_id, node_id, mastery) VALUES (?, ?, 0.0)',
                (user_id, node_id)
            )

        conn.commit()
        print(f"用户 {user_id} 的掌握度表初始化完成")

        # Also initialize dim-level params
        init_user_dim_params(user_id)

    except Exception as e:
        print(f"初始化用户掌握度失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def set_chapter_mastery(user_id: str, chapter_id: int, initial_mastery: float = 0.5):
    """
    设置某章节下所有知识点的初始掌握度

    Args:
        user_id: 用户ID
        chapter_id: 章节ID
        initial_mastery: 初始掌握度（默认0.5）
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Update user_mastery table
        cursor.execute(
            '''UPDATE user_mastery
               SET mastery      = ?,
                   last_updated = CURRENT_TIMESTAMP
               WHERE user_id = ?
                 AND node_id IN (SELECT id
                                 FROM knowledge_nodes
                                 WHERE chapter_id = ?)''',
            (initial_mastery, user_id, chapter_id)
        )

        # Also set dim-level params for nodes in this chapter
        cursor.execute(
            '''SELECT id FROM knowledge_nodes WHERE chapter_id = ?''',
            (chapter_id,)
        )
        node_ids = [row[0] for row in cursor.fetchall()]
        alpha = initial_mastery * 10.0 + 1.0
        beta_val = (1.0 - initial_mastery) * 10.0 + 1.0
        for node_id in node_ids:
            cursor.execute(
                'SELECT dim_id FROM skill_dimensions WHERE parent_node_id = ?',
                (node_id,)
            )
            for (dim_id,) in cursor.fetchall():
                cursor.execute(
                    '''INSERT INTO user_dim_params (user_id, dim_id, alpha, beta, stuck_count)
                       VALUES (?, ?, ?, ?, 0)
                       ON CONFLICT(user_id, dim_id)
                       DO UPDATE SET alpha = ?, beta = ?, last_updated = CURRENT_TIMESTAMP''',
                    (user_id, dim_id, alpha, beta_val, alpha, beta_val)
                )

        conn.commit()
        print(f"用户 {user_id} 章节 {chapter_id} 的掌握度已设置为 {initial_mastery}")

    except Exception as e:
        print(f"设置章节掌握度失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def set_nodes_mastery(user_id: str, node_mastery: dict):
    """
    Bulk-set mastery values for specific knowledge nodes during initialization.

    Args:
        user_id: 用户ID
        node_mastery: {node_id: mastery_value, ...} dict with mastery in [0.0, 1.0]
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        for node_id, mastery in node_mastery.items():
            clamped = max(0.0, min(1.0, float(mastery)))
            # Update user_mastery table
            cursor.execute(
                '''UPDATE user_mastery
                   SET mastery = ?,
                       last_updated = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND node_id = ?''',
                (clamped, user_id, node_id)
            )
            # Also set dim-level params
            alpha = clamped * 10.0 + 1.0
            beta_val = (1.0 - clamped) * 10.0 + 1.0
            cursor.execute(
                'SELECT dim_id FROM skill_dimensions WHERE parent_node_id = ?',
                (node_id,)
            )
            for (dim_id,) in cursor.fetchall():
                cursor.execute(
                    '''INSERT INTO user_dim_params (user_id, dim_id, alpha, beta, stuck_count)
                       VALUES (?, ?, ?, ?, 0)
                       ON CONFLICT(user_id, dim_id)
                       DO UPDATE SET alpha = ?, beta = ?, last_updated = CURRENT_TIMESTAMP''',
                    (user_id, dim_id, alpha, beta_val, alpha, beta_val)
                )

        conn.commit()

    except Exception as e:
        print(f"设置节点掌握度失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def update_mastery(user_id: str, node_id: int, delta: float = 0.1) -> float:
    """
    更新用户对某个知识点的掌握度（路由到维度级别的Bayesian更新）

    Args:
        user_id: 用户ID
        node_id: 知识点ID
        delta: 掌握度增量（默认0.1）

    Returns:
        更新后的掌握度值
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Get dimensions for this node
        cursor.execute(
            'SELECT dim_id, node_weight FROM skill_dimensions WHERE parent_node_id = ?',
            (node_id,)
        )
        dims = [(row[0], row[1]) for row in cursor.fetchall()]

        if dims:
            # Route through dim-level Bayesian update
            # Scale delta to Bayesian signal: delta=0.1 maps to meaningful evidence
            outcome = 'correct' if delta >= 0 else 'wrong'
            total_weight = abs(delta) * 50.0
            for dim_id, dim_weight in dims:
                signal = total_weight * dim_weight / sum(w for _, w in dims)
                apply_bayesian_feedback(user_id, dim_id, outcome,
                                        signal_weight=signal, _conn=conn)
                if delta > 0:
                    propagate_to_siblings(user_id, dim_id, signal * 0.3, _conn=conn)

        # Compute derived mastery from dims within the same connection
        new_mastery = 0.0
        if dims:
            wsum = 0.0
            for dim_id, dim_weight in dims:
                cursor.execute(
                    'SELECT alpha, beta FROM user_dim_params WHERE user_id = ? AND dim_id = ?',
                    (user_id, dim_id)
                )
                row = cursor.fetchone()
                if row:
                    a, b = row[0], row[1]
                    wsum += dim_weight
                    new_mastery += (a / (a + b)) * dim_weight
            if wsum > 0:
                new_mastery /= wsum
        else:
            new_mastery = 0.5

        # Sync to user_mastery table
        cursor.execute(
            '''INSERT INTO user_mastery (user_id, node_id, mastery)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, node_id)
               DO UPDATE SET mastery = ?, last_updated = CURRENT_TIMESTAMP''',
            (user_id, node_id, new_mastery, new_mastery)
        )
        conn.commit()
        return new_mastery

    except Exception as e:
        print(f"更新掌握度失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_mastery(user_id: str, node_id: int) -> float:
    """
    获取用户对某个知识点的掌握度（从维度参数衍生）

    Args:
        user_id: 用户ID
        node_id: 知识点ID

    Returns:
        掌握度值（0~1），如果不存在则返回0.0
    """
    try:
        return get_node_mastery_derived(user_id, node_id)
    except Exception as e:
        print(f"查询掌握度失败: {e}")
        raise


def get_user_learned_nodes(user_id: str, threshold: float = 0.7) -> List[int]:
    """
    获取用户已掌握的知识点ID列表（掌握度超过阈值）

    Args:
        user_id: 用户ID
        threshold: 掌握度阈值（默认0.7）

    Returns:
        已掌握知识点ID列表
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            '''SELECT node_id
               FROM user_mastery
               WHERE user_id = ?
                 AND mastery >= ?
               ORDER BY node_id''',
            (user_id, threshold)
        )
        rows = cursor.fetchall()

        return [row[0] for row in rows]

    except Exception as e:
        print(f"查询已掌握知识点失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_all_user_mastery(user_id: str) -> Dict[int, float]:
    """
    获取用户所有知识点的掌握度（从维度参数衍生）

    Args:
        user_id: 用户ID

    Returns:
        字典，键为知识点ID，值为掌握度
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM knowledge_nodes')
        nodes = [row[0] for row in cursor.fetchall()]
        result = {}
        for node_id in nodes:
            result[node_id] = get_node_mastery_derived(user_id, node_id)
        return result
    except Exception as e:
        print(f"查询用户掌握度失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_all_nodes_text() -> str:
    """
    获取所有知识点ID和名称的格式化文本，用于LLM提示词

    Returns:
        格式化字符串，如 "1: 函数与初等函数\n2: 极限的ε-δ定义\n..."
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM knowledge_nodes ORDER BY id')
        rows = cursor.fetchall()
        return "\n".join(f"{row[0]}: {row[1]}" for row in rows)
    except Exception as e:
        print(f"获取节点文本失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_chapters() -> List[Dict]:
    """
    获取所有章节列表

    Returns:
        章节列表，每个元素包含 chapter_id 和 chapter_name
    """
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 假设 chapter_id 对应不同的章节，这里需要根据实际情况调整
        cursor.execute('''
                       SELECT DISTINCT chapter_id,
                                       CASE chapter_id
                                           WHEN 1 THEN '函数与极限'
                                           WHEN 2 THEN '导数与微分'
                                           WHEN 3 THEN '积分学'
                                           ELSE '其他'
                                           END as chapter_name
                       FROM knowledge_nodes
                       WHERE chapter_id IS NOT NULL
                       ORDER BY chapter_id
                       ''')
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    except Exception as e:
        print(f"查询章节列表失败: {e}")
        raise
    finally:
        if conn:
            conn.close()

def reset_user_mastery(user_id: str):
    """
    重置用户所有知识点的掌握度为0.0

    Args:
        user_id: 用户ID
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            'UPDATE user_mastery SET mastery = 0.0, last_updated = CURRENT_TIMESTAMP WHERE user_id = ?',
            (user_id,)
        )

        conn.commit()
        print(f"用户 {user_id} 的掌握度已重置为0")

        # Also reset dim params
        reset_user_dim_params(user_id)

    except Exception as e:
        print(f"重置用户掌握度失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# ===== Dimension-level API =====

def get_all_dimensions() -> List[Dict]:
    """Get all skill dimensions."""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM skill_dimensions ORDER BY dim_id')
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"查询所有维度失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_dimension(dim_id: str) -> Optional[Dict]:
    """Get a single skill dimension by ID."""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM skill_dimensions WHERE dim_id = ?', (dim_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"查询维度失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_dimensions_for_node(node_id: int) -> List[Dict]:
    """Get all dimensions belonging to a knowledge node."""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM skill_dimensions WHERE parent_node_id = ? ORDER BY dim_id',
            (node_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"查询节点维度失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_user_dim_params(user_id: str):
    """Initialize Beta(1,1) for all dimensions for a user."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT dim_id FROM skill_dimensions')
        dims = [row[0] for row in cursor.fetchall()]
        for dim_id in dims:
            cursor.execute(
                '''INSERT OR IGNORE INTO user_dim_params
                   (user_id, dim_id, alpha, beta, stuck_count)
                   VALUES (?, ?, 1.0, 1.0, 0)''',
                (user_id, dim_id)
            )
        conn.commit()
        print(f"用户 {user_id} 的维度参数初始化完成 ({len(dims)} 个维度)")
    except Exception as e:
        print(f"初始化用户维度参数失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def apply_bayesian_feedback(user_id: str, dim_id: str, outcome: str,
                            signal_weight: float = 1.0,
                            _conn: Optional[sqlite3.Connection] = None) -> Dict:
    """Apply Bayesian update to a dimension's Beta distribution.

    Args:
        user_id: User ID
        dim_id: Dimension ID
        outcome: "correct", "wrong", or "stuck"
        signal_weight: Strength of the signal (default 1.0)
        _conn: Optional existing connection to reuse (avoids nested connections)

    Returns:
        dict with alpha, beta, new_mastery
    """
    own_conn = _conn is None
    try:
        conn = _conn if _conn is not None else sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT alpha, beta, stuck_count FROM user_dim_params WHERE user_id = ? AND dim_id = ?',
            (user_id, dim_id)
        )
        row = cursor.fetchone()

        if row is None:
            # Initialize if missing
            alpha, beta_val, stuck_count = 1.0, 1.0, 0
            cursor.execute(
                '''INSERT INTO user_dim_params (user_id, dim_id, alpha, beta, stuck_count)
                   VALUES (?, ?, ?, ?, ?)''',
                (user_id, dim_id, alpha, beta_val, stuck_count)
            )
        else:
            alpha, beta_val, stuck_count = row[0], row[1], row[2]

        if outcome == 'correct':
            alpha += signal_weight
        elif outcome == 'wrong':
            beta_val += signal_weight
        elif outcome == 'stuck':
            beta_val += signal_weight * 0.5
            stuck_count += 1

        cursor.execute(
            '''UPDATE user_dim_params
               SET alpha = ?, beta = ?, stuck_count = ?, last_updated = CURRENT_TIMESTAMP
               WHERE user_id = ? AND dim_id = ?''',
            (alpha, beta_val, stuck_count, user_id, dim_id)
        )

        if own_conn:
            conn.commit()
        mastery = alpha / (alpha + beta_val)
        return {'dim_id': dim_id, 'alpha': alpha, 'beta': beta_val,
                'mastery': round(mastery, 4), 'stuck_count': stuck_count}
    except Exception as e:
        print(f"Bayesian反馈更新失败: {e}")
        if conn and own_conn:
            conn.rollback()
        raise
    finally:
        if conn and own_conn:
            conn.close()


def get_dim_mastery(user_id: str, dim_id: str) -> float:
    """Get mastery for a dimension: alpha / (alpha + beta)."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT alpha, beta FROM user_dim_params WHERE user_id = ? AND dim_id = ?',
            (user_id, dim_id)
        )
        row = cursor.fetchone()
        if row is None:
            return 0.0
        alpha, beta_val = row[0], row[1]
        return alpha / (alpha + beta_val) if (alpha + beta_val) > 0 else 0.0
    except Exception as e:
        print(f"查询维度掌握度失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_dim_confidence(user_id: str, dim_id: str) -> float:
    """Get confidence for a dimension: alpha + beta (higher = more data)."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT alpha, beta FROM user_dim_params WHERE user_id = ? AND dim_id = ?',
            (user_id, dim_id)
        )
        row = cursor.fetchone()
        if row is None:
            return 0.0
        return row[0] + row[1]
    except Exception as e:
        print(f"查询维度置信度失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_dim_stuck_count(user_id: str, dim_id: str) -> int:
    """Get stuck count for a dimension."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT stuck_count FROM user_dim_params WHERE user_id = ? AND dim_id = ?',
            (user_id, dim_id)
        )
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception as e:
        print(f"查询卡住次数失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_node_mastery_derived(user_id: str, node_id: int) -> float:
    """Compute node mastery as weighted average of its dimensions' mastery."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT dim_id, node_weight FROM skill_dimensions WHERE parent_node_id = ?',
            (node_id,)
        )
        dims = [(row[0], row[1]) for row in cursor.fetchall()]
        if not dims:
            # Fallback to user_mastery table
            cursor.execute(
                'SELECT mastery FROM user_mastery WHERE user_id = ? AND node_id = ?',
                (user_id, node_id)
            )
            row = cursor.fetchone()
            return row[0] if row else 0.0

        total, wsum = 0.0, 0.0
        for dim_id, weight in dims:
            m = get_dim_mastery(user_id, dim_id)
            total += m * weight
            wsum += weight
        return total / wsum if wsum > 0 else 0.0
    except Exception as e:
        print(f"计算节点衍生掌握度失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


def propagate_to_siblings(user_id: str, dim_id: str, gain: float,
                         _conn: Optional[sqlite3.Connection] = None) -> list:
    """Propagate a gain from one dimension to related dimensions via skill_edges.

    Returns:
        list of (to_dim_id, propagated_delta) pairs for compensation event tracking (L3).
    """
    own_conn = _conn is None
    results = []
    try:
        conn = _conn if _conn is not None else sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT to_dim, transfer_gain FROM skill_edges WHERE from_dim = ?',
            (dim_id,)
        )
        edges = cursor.fetchall()
        for to_dim, transfer_gain in edges:
            propagated = gain * transfer_gain * 0.5
            if propagated > 0.001:
                apply_bayesian_feedback(user_id, to_dim, 'correct',
                                        signal_weight=propagated, _conn=conn)
                results.append((to_dim, round(propagated, 6)))
        if own_conn:
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"传播到关联维度失败: {e}")
        if own_conn and conn:
            conn.rollback()
            conn.close()
        raise
    return results


def reset_user_dim_params(user_id: str):
    """Reset all dimension params for a user to Beta(1,1)."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            '''UPDATE user_dim_params
               SET alpha = 1.0, beta = 1.0, stuck_count = 0,
                   last_updated = CURRENT_TIMESTAMP
               WHERE user_id = ?''',
            (user_id,)
        )
        conn.commit()
        print(f"用户 {user_id} 的维度参数已重置")
    except Exception as e:
        print(f"重置用户维度参数失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def ensure_user_meta_table():
    """Create user_meta table if it does not exist."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_meta (
                user_id TEXT PRIMARY KEY,
                momentum REAL NOT NULL DEFAULT 0.0,
                state_json TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"创建 user_meta 表失败: {e}")
        raise


def get_user_meta(user_id: str) -> dict:
    """Get user metadata (momentum, state_json)."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT momentum, state_json FROM user_meta WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'momentum': row[0], 'state_json': row[1]}
        return {'momentum': 0.0, 'state_json': None}
    except Exception as e:
        print(f"获取用户元数据失败: {e}")
        raise


def update_momentum_db(user_id: str, outcome_value: float):
    """Update user momentum with exponential moving average.
    outcome_value: correct=+0.15, wrong=-0.1, stuck=-0.3, breakthrough=+0.5
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT momentum FROM user_meta WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        current = row[0] if row else 0.0
        new_momentum = current * 0.85 + outcome_value * 0.15
        new_momentum = max(-1.0, min(1.0, new_momentum))
        cursor.execute(
            '''INSERT INTO user_meta (user_id, momentum)
               VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET momentum = ?''',
            (user_id, new_momentum, new_momentum)
        )
        conn.commit()
        conn.close()
        return new_momentum
    except Exception as e:
        print(f"更新动量失败: {e}")
        raise


def get_all_user_dim_state(user_id: str) -> dict:
    """Get full user dim state for path planner: mastery and confidence per dim."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT dim_id, alpha, beta, stuck_count
               FROM user_dim_params WHERE user_id = ?''',
            (user_id,)
        )
        dims = {}
        for dim_id, alpha, beta_val, stuck_count in cursor.fetchall():
            mastery = alpha / (alpha + beta_val) if (alpha + beta_val) > 0 else 0.0
            dims[dim_id] = {
                'mastery': round(mastery, 4),
                'confidence': round(alpha + beta_val, 2),
                'stuck_count': stuck_count,
            }
        conn.close()
        return dims
    except Exception as e:
        print(f"获取用户维度状态失败: {e}")
        raise


def get_user_state_summary(user_id: str) -> dict:
    """Get summary stats for the user."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM skill_dimensions')
        dim_count = cursor.fetchone()[0]
        cursor.execute(
            '''SELECT dim_id, alpha, beta FROM user_dim_params WHERE user_id = ?''',
            (user_id,)
        )
        rows = cursor.fetchall()
        weak_dims = 0
        total_mastery = 0.0
        for dim_id, alpha, beta_val in rows:
            m = alpha / (alpha + beta_val) if (alpha + beta_val) > 0 else 0.0
            total_mastery += m
            if m < 0.5:
                weak_dims += 1
        avg_mastery = round(total_mastery / len(rows), 3) if rows else 0.0
        meta = get_user_meta(user_id)
        conn.close()
        return {
            'dim_count': dim_count,
            'weak_dims': weak_dims,
            'avg_mastery': avg_mastery,
            'momentum': round(meta['momentum'], 3),
        }
    except Exception as e:
        print(f"获取用户状态摘要失败: {e}")
        raise


def sync_node_mastery_from_dims(user_id: str):
    """Update user_mastery table with derived values from dim params."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM knowledge_nodes')
        nodes = [row[0] for row in cursor.fetchall()]
        for node_id in nodes:
            derived = get_node_mastery_derived(user_id, node_id)
            cursor.execute(
                '''INSERT INTO user_mastery (user_id, node_id, mastery)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, node_id)
                   DO UPDATE SET mastery = ?, last_updated = CURRENT_TIMESTAMP''',
                (user_id, node_id, derived, derived)
            )
        conn.commit()
    except Exception as e:
        print(f"同步节点掌握度失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def reset_database():
    """
    重置整个数据库：删除所有表并重新从CSV文件导入数据。
    这会清除所有用户掌握度数据。
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # 删除所有表
        cursor.execute('DROP TABLE IF EXISTS user_meta')
        cursor.execute('DROP TABLE IF EXISTS user_dim_params')
        cursor.execute('DROP TABLE IF EXISTS skill_edges')
        cursor.execute('DROP TABLE IF EXISTS skill_dimensions')
        cursor.execute('DROP TABLE IF EXISTS user_mastery')
        cursor.execute('DROP TABLE IF EXISTS practice_sessions')
        cursor.execute('DROP TABLE IF EXISTS prerequisites')
        cursor.execute('DROP TABLE IF EXISTS knowledge_nodes')

        conn.commit()
        print("所有表已删除")

    except Exception as e:
        print(f"删除表失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

    # 重新导入CSV数据（复用init_db的表创建和数据导入逻辑）
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # 重新创建表
        cursor.execute('''
                       CREATE TABLE knowledge_nodes
                       (
                           id         INTEGER PRIMARY KEY,
                           name       TEXT    NOT NULL,
                           difficulty INTEGER NOT NULL,
                           chapter_id INTEGER
                       )
                       ''')

        cursor.execute('''
                       CREATE TABLE prerequisites
                       (
                           from_id INTEGER NOT NULL,
                           to_id   INTEGER NOT NULL,
                           PRIMARY KEY (from_id, to_id)
                       )
                       ''')

        cursor.execute('''
                       CREATE TABLE user_mastery
                       (
                           user_id      TEXT    NOT NULL,
                           node_id      INTEGER NOT NULL,
                           mastery      REAL    NOT NULL DEFAULT 0.0 CHECK (mastery >= 0 AND mastery <= 1.0),
                           last_updated TIMESTAMP        DEFAULT CURRENT_TIMESTAMP,
                           PRIMARY KEY (user_id, node_id),
                           FOREIGN KEY (node_id) REFERENCES knowledge_nodes (id)
                       )
                       ''')

        cursor.execute('''
                       CREATE TABLE practice_sessions
                       (
                           id              INTEGER PRIMARY KEY AUTOINCREMENT,
                           user_id         TEXT    NOT NULL,
                           target_nodes    TEXT    NOT NULL,
                           questions_json  TEXT    NOT NULL,
                           results_json    TEXT    NOT NULL,
                           average_score   REAL    NOT NULL DEFAULT 0.0,
                           total_questions INTEGER NOT NULL DEFAULT 0,
                           created_at      TIMESTAMP        DEFAULT CURRENT_TIMESTAMP
                       )
                       ''')

        # Create dimension-level tables
        ensure_skill_dimensions_table()
        ensure_skill_edges_table()
        ensure_user_dim_params_table()

        # 重新导入knowledge_nodes数据
        with open('data/knowledge_nodes.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = int(row['id'])
                if node_id <= 8:
                    chapter_id = 1
                elif node_id <= 15:
                    chapter_id = 2
                elif node_id <= 23:
                    chapter_id = 3
                else:
                    chapter_id = None

                cursor.execute(
                    'INSERT INTO knowledge_nodes (id, name, difficulty, chapter_id) VALUES (?, ?, ?, ?)',
                    (node_id, row['name'], int(row['difficulty']), chapter_id)
                )

        # 重新导入prerequisites数据
        with open('data/prerequisites.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    'INSERT INTO prerequisites (from_id, to_id) VALUES (?, ?)',
                    (int(row['from_id']), int(row['to_id']))
                )

        conn.commit()
        print("数据库重置完成：所有表已重建，CSV数据已重新导入")

        # Run dimension migrations
        migrate_skill_dimensions()

    except FileNotFoundError as e:
        print(f"文件未找到: {e}")
        raise
    except Exception as e:
        print(f"数据库重置失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def diagnose_and_update_mastery(user_id: str, node_id: int, student_answer: str) -> Dict:
    """
    诊断学生回答并更新掌握度

    Args:
        user_id: 用户ID
        node_id: 知识点ID
        student_answer: 学生的回答

    Returns:
        包含评分、评语和新掌握度的字典
    """
    import llm_api

    try:
        # 获取知识点名称
        node = get_node(node_id)
        if not node:
            return {'error': f'知识点ID {node_id} 不存在'}

        knowledge_point = node['name']

        # 调用LLM诊断
        result = llm_api.diagnose_mastery(knowledge_point, student_answer)

        # 检查返回值是否有效
        if result is None or not isinstance(result, tuple) or len(result) != 2:
            return {'error': 'LLM诊断返回格式错误'}

        score, comment = result

        # 验证评分有效性
        if not isinstance(score, int) or score < 1 or score > 5:
            return {'error': f'无效的评分: {score}'}

        # 将评分(1-5)映射为掌握度(0-1)
        mastery_value = (score - 1) / 4.0

        # 获取当前掌握度
        current_mastery = get_mastery(user_id, node_id)

        # 计算增量并更新
        delta = mastery_value - current_mastery
        new_mastery = update_mastery(user_id, node_id, delta=delta)

        return {
            'score': score,
            'comment': comment if comment else '评估完成',
            'mastery': new_mastery
        }

    except Exception as e:
        print(f"诊断并更新掌握度失败: {e}")
        import traceback
        traceback.print_exc()
        return {'error': f'诊断失败: {str(e)}'}


# ===== Admin functions =====

def get_all_users() -> List[Dict]:
    """Return all users with mastery stats and practice count."""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id,
                   COUNT(*) AS nodes_learned,
                   ROUND(AVG(mastery), 3) AS avg_mastery,
                   MAX(last_updated) AS last_active
            FROM user_mastery
            GROUP BY user_id
            ORDER BY last_active DESC
        ''')
        users = [dict(row) for row in cursor.fetchall()]
        for u in users:
            cursor.execute(
                'SELECT COUNT(*) FROM practice_sessions WHERE user_id = ?',
                (u['user_id'],)
            )
            u['practice_count'] = cursor.fetchone()[0]
        conn.close()
        return users
    except Exception as e:
        print(f"获取用户列表失败: {e}")
        return []


def delete_user_data(user_id: str):
    """Delete all data for a given user."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_meta WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM user_mastery WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM user_dim_params WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM practice_sessions WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"删除用户数据失败: {e}")
        raise


def get_user_dim_mastery_all(user_id: str) -> List[Dict]:
    """Returns all dim-level mastery data for a user."""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT d.dim_id, d.name, d.parent_node_id,
                   COALESCE(kn.name, '') as parent_node_name,
                   kn.chapter_id,
                   COALESCE(udp.alpha, 1.0) as alpha,
                   COALESCE(udp.beta, 1.0) as beta,
                   COALESCE(udp.stuck_count, 0) as stuck_count,
                   d.difficulty
            FROM skill_dimensions d
            LEFT JOIN knowledge_nodes kn ON d.parent_node_id = kn.id
            LEFT JOIN user_dim_params udp ON d.dim_id = udp.dim_id AND udp.user_id = ?
            ORDER BY d.parent_node_id, d.dim_id
        ''', (user_id,)).fetchall()
        conn.close()

        result = []
        for row in rows:
            alpha = row['alpha'] or 1.0
            beta = row['beta'] or 1.0
            mastery = alpha / (alpha + beta) if (alpha + beta) > 0 else 0.0
            confidence = alpha + beta
            result.append({
                'dim_id': row['dim_id'],
                'name': row['name'],
                'parent_node_id': row['parent_node_id'],
                'parent_node_name': row['parent_node_name'],
                'chapter_id': row['chapter_id'],
                'mastery': round(mastery, 4),
                'confidence': round(confidence, 2),
                'alpha': round(alpha, 2),
                'beta': round(beta, 2),
                'stuck_count': row['stuck_count'],
                'difficulty': row['difficulty']
            })
        return result
    except Exception as e:
        print(f"获取用户维度掌握度失败: {e}")
        return []


def get_user_node_mastery_derived_all(user_id: str) -> List[Dict]:
    """Returns all node-level derived mastery for a user."""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT kn.id as node_id, kn.name, kn.chapter_id,
                   COALESCE(um.mastery, 0.0) as mastery
            FROM knowledge_nodes kn
            LEFT JOIN user_mastery um ON kn.id = um.node_id AND um.user_id = ?
            ORDER BY kn.id
        ''', (user_id,)).fetchall()
        conn.close()

        return [{
            'node_id': row['node_id'],
            'name': row['name'],
            'chapter_id': row['chapter_id'],
            'mastery': round(row['mastery'], 4)
        } for row in rows]
    except Exception as e:
        print(f"获取用户节点掌握度失败: {e}")
        return []

