import sqlite3
import csv
import os
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

        # 更新该章节下所有知识点的掌握度
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


def update_mastery(user_id: str, node_id: int, delta: float = 0.1) -> float:
    """
    更新用户对某个知识点的掌握度

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

        # 获取当前掌握度
        cursor.execute(
            'SELECT mastery FROM user_mastery WHERE user_id = ? AND node_id = ?',
            (user_id, node_id)
        )
        row = cursor.fetchone()

        if row is None:
            # 如果记录不存在，创建新记录
            current_mastery = 0.0
            cursor.execute(
                'INSERT INTO user_mastery (user_id, node_id, mastery) VALUES (?, ?, ?)',
                (user_id, node_id, current_mastery)
            )
        else:
            current_mastery = row[0]

        # 计算新掌握度（上限1.0）
        new_mastery = min(1.0, current_mastery + delta)

        # 更新数据库
        cursor.execute(
            '''UPDATE user_mastery
               SET mastery      = ?,
                   last_updated = CURRENT_TIMESTAMP
               WHERE user_id = ?
                 AND node_id = ?''',
            (new_mastery, user_id, node_id)
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
    获取用户对某个知识点的掌握度

    Args:
        user_id: 用户ID
        node_id: 知识点ID

    Returns:
        掌握度值（0~1），如果不存在则返回0.0
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT mastery FROM user_mastery WHERE user_id = ? AND node_id = ?',
            (user_id, node_id)
        )
        row = cursor.fetchone()

        return row[0] if row else 0.0

    except Exception as e:
        print(f"查询掌握度失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


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
    获取用户所有知识点的掌握度

    Args:
        user_id: 用户ID

    Returns:
        字典，键为知识点ID，值为掌握度
    """
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT node_id, mastery FROM user_mastery WHERE user_id = ?',
            (user_id,)
        )
        rows = cursor.fetchall()

        return {row[0]: row[1] for row in rows}

    except Exception as e:
        print(f"查询用户掌握度失败: {e}")
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

