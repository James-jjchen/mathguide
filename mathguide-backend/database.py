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
            cursor.execute(
                '''UPDATE user_mastery
                   SET mastery = ?,
                       last_updated = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND node_id = ?''',
                (clamped, user_id, node_id)
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

    except Exception as e:
        print(f"重置用户掌握度失败: {e}")
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
        cursor.execute('DROP TABLE IF EXISTS user_mastery')
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
        cursor.execute('DELETE FROM user_mastery WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM practice_sessions WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"删除用户数据失败: {e}")
        raise

