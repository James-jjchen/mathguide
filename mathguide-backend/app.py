from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import database
import recommend
import llm_api
import json
import os
import secrets
import functools

# 创建Flask应用实例
app = Flask(__name__)
# 启用CORS，允许前端跨域访问
CORS(app)

# 后台处理防抖：正在处理的user_id集合，避免重复触发
_bg_processing = set()

# Admin authentication
ADMIN_USERNAME = os.environ.get('MATHGUIDE_ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('MATHGUIDE_ADMIN_PASS', 'mathguide2024')
_admin_tokens = set()

def _require_admin(f):
    """Decorator that checks for a valid admin token in the Authorization header."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer ') or auth[7:] not in _admin_tokens:
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return wrapper

@app.route('/api/nodes', methods=['GET'])
def get_all_nodes():
    """
    获取所有知识点列表

    Returns:
        JSON格式的所有知识点列表
    """
    try:
        nodes = database.get_all_nodes()
        return jsonify(nodes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/node/<int:node_id>', methods=['GET'])
def get_single_node(node_id):
    """
    获取单个知识点详情

    Args:
        node_id: 知识点ID

    Returns:
        JSON格式的知识点详情，如果不存在则返回404
    """
    try:
        node = database.get_node(node_id)
        if node:
            return jsonify(node)
        else:
            return jsonify({'error': '知识点未找到'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters', methods=['GET'])
def get_chapters():
    """
    获取所有章节列表

    Returns:
        JSON格式的章节列表
    """
    try:
        chapters = database.get_chapters()
        return jsonify(chapters)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/init_user', methods=['POST'])
def init_user():
    """
    初始化用户并设置已学知识点

    Expected JSON input (new format with node-level mastery):
        {
            "user_id": "student_001",
            "node_mastery": {1: 0.7, 2: 0.4, 3: 0.0, ...}
        }

    Or legacy format (still supported):
        {
            "user_id": "student_001",
            "chapter_ids": [1, 2]
        }

    Returns:
        {"message": "初始化成功", "learned_nodes": [1, 2, 3, ...]}
    """
    try:
        data = request.get_json()

        if not data or 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        user_id = data['user_id']
        node_mastery = data.get('node_mastery', None)
        chapter_ids = data.get('chapter_ids', [])

        # 初始化用户掌握度表 (all zeros)
        database.init_user_mastery(user_id)

        if node_mastery and isinstance(node_mastery, dict):
            # New approach: fine-grained node-level mastery
            database.set_nodes_mastery(user_id, node_mastery)
        elif chapter_ids:
            if not isinstance(chapter_ids, list):
                return jsonify({'error': 'chapter_ids必须是数组'}), 400
            # Legacy approach: uniform chapter-level mastery
            for chapter_id in chapter_ids:
                database.set_chapter_mastery(user_id, chapter_id, initial_mastery=0.5)

        # 获取已掌握的知识点列表
        learned_nodes = database.get_user_learned_nodes(user_id, threshold=0.5)

        return jsonify({
            'message': '初始化成功',
            'user_id': user_id,
            'learned_nodes': learned_nodes
        })

    except Exception as e:
        return jsonify({'error': f'初始化用户时出错: {str(e)}'}), 500

@app.route('/api/ask', methods=['POST'])
def ask_question():
    """
    数学问题问答接口（带知识边界和掌握度更新）

    Expected JSON input:
        {
            "question": "问题内容",
            "user_id": "student_001",
            "learned_ids": [1, 2, 3]
        }

    Returns:
        {
            "answer": "回答内容",
            "updated_mastery": {"node_id": new_mastery}
        }
    """
    try:
        data = request.get_json()

        # 验证输入数据
        if not data or 'question' not in data:
            return jsonify({'error': '缺少question字段'}), 400

        question = data['question']
        if not question or not question.strip():
            return jsonify({'error': '问题内容不能为空'}), 400

        # 获取用户ID（可选）
        user_id = data.get('user_id', None)

        # 获取已学知识点ID列表
        learned_ids = data.get('learned_ids', None)

        # 验证learned_ids格式（如果提供）
        if learned_ids is not None:
            if not isinstance(learned_ids, list):
                return jsonify({'error': 'learned_ids必须是数组'}), 400
            learned_ids = [int(x) for x in learned_ids if isinstance(x, (int, float))]

        # 调用LLM获取回答（唯一阻塞调用）
        answer = llm_api.ask_math_question_with_boundary(question, learned_ids)

        # 后台线程：防抖，同一用户正在处理时跳过
        if user_id:
            import threading
            def background_infer_and_update():
                if user_id in _bg_processing:
                    return
                _bg_processing.add(user_id)
                try:
                    involved = llm_api.infer_nodes_from_question_llm(question)
                    quality_score, quality_reason = llm_api.evaluate_question_quality(question)
                    print(f"问题质量评分: {quality_score}/10 - {quality_reason}")
                    quality_factor = (quality_score - 5) / 5.0  # -1.0 to 1.0
                    for node in involved:
                        delta = node['confidence'] * quality_factor * 0.15
                        database.update_mastery(user_id, node['node_id'], delta=delta)
                except Exception as e:
                    print(f"后台掌握度更新失败: {e}")
                finally:
                    _bg_processing.discard(user_id)

            t = threading.Thread(target=background_infer_and_update, daemon=True)
            t.start()

        return jsonify({'answer': answer})

    except Exception as e:
        return jsonify({'error': f'处理问题时出错: {str(e)}'}), 500

@app.route('/api/ask/stream', methods=['POST'])
def ask_question_stream():
    """
    流式数学问题问答接口（SSE）

    Expected JSON input: same as /api/ask
        {
            "question": "问题内容",
            "user_id": "student_001",
            "learned_ids": [1, 2, 3]
        }

    Returns:
        text/event-stream, 每个token一个SSE事件
    """
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({'error': '缺少question字段'}), 400

    question = data['question']
    if not question or not question.strip():
        return jsonify({'error': '问题内容不能为空'}), 400

    user_id = data.get('user_id', None)
    learned_ids = data.get('learned_ids', None)
    if learned_ids is not None:
        if not isinstance(learned_ids, list):
            return jsonify({'error': 'learned_ids必须是数组'}), 400
        learned_ids = [int(x) for x in learned_ids if isinstance(x, (int, float))]

    def generate():
        for chunk in llm_api.ask_math_question_stream(question, learned_ids):
            yield chunk

        # 流结束后后台更新掌握度
        if user_id:
            import threading
            def bg_update():
                if user_id in _bg_processing:
                    return
                _bg_processing.add(user_id)
                try:
                    involved = llm_api.infer_nodes_from_question_llm(question)
                    quality_score, quality_reason = llm_api.evaluate_question_quality(question)
                    quality_factor = (quality_score - 5) / 5.0
                    for node in involved:
                        delta = node['confidence'] * quality_factor * 0.15
                        database.update_mastery(user_id, node['node_id'], delta=delta)
                except Exception as e:
                    print(f"后台掌握度更新失败: {e}")
                finally:
                    _bg_processing.discard(user_id)

            t = threading.Thread(target=bg_update, daemon=True)
            t.start()

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/api/recommend', methods=['POST'])
def get_recommendation():
    """
    学习路径推荐接口（基于掌握度的自适应推荐）

    Expected JSON input:
        {
            "user_id": "student_001",
            "strategy": "auto" 或 "review" 或 "next"
        }

    Returns:
        {
            "recommended_id": 推荐的知识点ID,
            "node": 推荐的知识点详情,
            "message": 提示信息,
            "recommend_type": "review" 或 "new"
        }
    """
    try:
        data = request.get_json()

        # 验证输入数据
        if not data or 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        user_id = data['user_id']

        # 获取推荐策略，默认为'auto'（自动选择复习或新知识）
        strategy = data.get('strategy', 'auto')
        if strategy not in ['auto', 'review', 'next']:
            return jsonify({'error': 'strategy必须是"auto"、"review"或"next"'}), 400

        # 获取用户所有掌握度
        all_mastery = database.get_all_user_mastery(user_id)

        recommended_id = None
        recommend_type = None

        # 策略1：复习薄弱点（掌握度 < 0.5）
        if strategy in ['auto', 'review']:
            weak_nodes = [(node_id, mastery) for node_id, mastery in all_mastery.items() if mastery < 0.5]
            if weak_nodes:
                # 按掌握度升序排序（最差的先复习）
                weak_nodes.sort(key=lambda x: x[1])
                recommended_id = weak_nodes[0][0]
                recommend_type = 'review'
                print(f"推荐复习薄弱知识点: {recommended_id}, 掌握度: {weak_nodes[0][1]}")

        # 策略2：推荐新知识点（如果没有薄弱点或策略为next）
        if recommended_id is None and strategy in ['auto', 'next']:
            # 找出掌握度 >= 0.7 的知识点作为已学
            learned_ids = [node_id for node_id, mastery in all_mastery.items() if mastery >= 0.7]

            # 如果没有掌握度>=0.7的，使用>=0.5的
            if not learned_ids:
                learned_ids = [node_id for node_id, mastery in all_mastery.items() if mastery >= 0.5]

            print(f"已学知识点（掌握度>=0.7）: {learned_ids}")

            # 调用推荐算法
            recommended_id = recommend.recommend_next(learned_ids, 'difficulty')
            if recommended_id:
                recommend_type = 'new'
                print(f"推荐新知识点: {recommended_id}")

        if recommended_id is None:
            return jsonify({
                'recommended_id': None,
                'node': None,
                'message': '没有可推荐的知识点，请先完成初始化或学习基础章节',
                'recommend_type': None
            })

        # 获取推荐节点的详细信息
        node = database.get_node(recommended_id)
        if node is None:
            return jsonify({
                'recommended_id': recommended_id,
                'node': None,
                'message': '推荐知识点ID存在但无法获取详情',
                'recommend_type': recommend_type
            })

        message = f"推荐成功 - {'复习薄弱点' if recommend_type == 'review' else '学习新知识'}"

        return jsonify({
            'recommended_id': recommended_id,
            'node': node,
            'message': message,
            'recommend_type': recommend_type
        })

    except Exception as e:
        return jsonify({'error': f'生成推荐时出错: {str(e)}'}), 500

@app.route('/api/mastery', methods=['GET'])
def get_user_mastery():
    """
    获取用户所有知识点的掌握度

    Expected query params:
        user_id: 用户ID

    Returns:
        {
            "user_id": "student_001",
            "mastery": {
                "1": 0.5,
                "2": 0.7,
                ...
            }
        }
    """
    try:
        user_id = request.args.get('user_id')

        if not user_id:
            return jsonify({'error': '缺少user_id参数'}), 400

        mastery = database.get_all_user_mastery(user_id)

        # 将key转换为字符串以便JSON序列化
        mastery_str = {str(k): v for k, v in mastery.items()}

        return jsonify({
            'user_id': user_id,
            'mastery': mastery_str
        })

    except Exception as e:
        return jsonify({'error': f'查询掌握度时出错: {str(e)}'}), 500


@app.route('/api/diagnose', methods=['POST'])
def diagnose_knowledge():
    """
    知识点掌握程度诊断接口（主动诊断）

    Expected JSON input:
        {
            "user_id": "student_001",
            "node_id": 5,
            "student_answer": "学生的回答"
        }

    Returns:
        {
            "score": 评分(1-5),
            "comment": "评语",
            "mastery": 新的掌握度
        }
    """
    try:
        data = request.get_json()

        # 验证输入数据
        if not data:
            return jsonify({'error': '缺少请求体'}), 400

        if 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        if 'node_id' not in data:
            return jsonify({'error': '缺少node_id字段'}), 400

        if 'student_answer' not in data:
            return jsonify({'error': '缺少student_answer字段'}), 400

        user_id = data['user_id']
        node_id = data['node_id']
        student_answer = data['student_answer']

        # 验证字段不为空
        if not student_answer or not student_answer.strip():
            return jsonify({'error': '学生回答不能为空'}), 400

        # 调用诊断并更新掌握度
        result = database.diagnose_and_update_mastery(user_id, node_id, student_answer)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify({
            'score': result['score'],
            'comment': result['comment'],
            'mastery': result['mastery']
        })

    except Exception as e:
        return jsonify({'error': f'诊断时出错: {str(e)}'}), 500


@app.route('/api/diagnose-weaknesses', methods=['POST'])
def diagnose_weaknesses():
    """
    诊断用户薄弱知识点（纯数据库查询，无需LLM）

    Expected JSON input:
        {
            "user_id": "student_001"
        }

    Returns:
        {
            "weaknesses": [{"node_id": 5, "name": "...", "mastery": 0.2, "priority": "high"}, ...],
            "strengths": [{"node_id": 1, "name": "...", "mastery": 0.85}, ...],
            "summary": {"overall_average": 0.45, "weak_count": 5, "strong_count": 3}
        }
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        user_id = data['user_id']
        all_mastery = database.get_all_user_mastery(user_id)

        if not all_mastery:
            return jsonify({
                'weaknesses': [],
                'strengths': [],
                'summary': {'overall_average': 0.0, 'weak_count': 0, 'strong_count': 0},
                'message': '用户尚未初始化，请先调用/api/init_user'
            })

        weaknesses = []
        strengths = []
        for node_id, mastery in all_mastery.items():
            node = database.get_node(node_id)
            if not node:
                continue
            entry = {'node_id': node_id, 'name': node['name'], 'mastery': round(mastery, 2)}
            if mastery < 0.5:
                if mastery < 0.2:
                    entry['priority'] = 'high'
                elif mastery < 0.35:
                    entry['priority'] = 'medium'
                else:
                    entry['priority'] = 'low'
                weaknesses.append(entry)
            elif mastery >= 0.7:
                strengths.append(entry)

        weaknesses.sort(key=lambda x: x['mastery'])
        strengths.sort(key=lambda x: x['mastery'], reverse=True)

        values = list(all_mastery.values())
        avg = round(sum(values) / len(values), 2) if values else 0.0

        return jsonify({
            'weaknesses': weaknesses,
            'strengths': strengths[:5],
            'summary': {
                'overall_average': avg,
                'weak_count': len(weaknesses),
                'strong_count': len(strengths),
                'total_nodes': len(values)
            }
        })

    except Exception as e:
        return jsonify({'error': f'诊断薄弱点时出错: {str(e)}'}), 500


@app.route('/api/generate-practice', methods=['POST'])
def generate_practice():
    """
    生成练习题接口

    Expected JSON input:
        {
            "user_id": "student_001",
            "node_ids": [2, 5],       # 可选，不提供则自动选最薄弱节点
            "count": 3                 # 可选，默认3
        }

    Returns:
        {
            "questions": [{"id": "q_2_...", "node_id": 2, "node_name": "...",
                          "type": "conceptual", "question_text": "...", "hint": "..."}, ...]
        }
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        user_id = data['user_id']
        node_ids = data.get('node_ids', None)
        count = data.get('count', 3)

        # 如果未指定node_ids，自动选择最薄弱的知识点
        if not node_ids:
            weak_nodes = recommend.get_weakest_nodes(user_id, threshold=0.5, limit=5)
            if not weak_nodes:
                return jsonify({
                    'questions': [],
                    'message': '没有薄弱知识点，您已掌握所有内容！'
                })
            node_ids = [n['node_id'] for n in weak_nodes[:min(len(weak_nodes), count)]]

        # 计算每个知识点的题目数
        count_per_node = max(1, count // len(node_ids)) if len(node_ids) > 0 else 1

        # 生成练习题
        questions = llm_api.generate_practice_questions(node_ids, count_per_node)

        return jsonify({
            'questions': questions,
            'target_nodes': node_ids
        })

    except Exception as e:
        return jsonify({'error': f'生成练习题时出错: {str(e)}'}), 500


@app.route('/api/submit-practice', methods=['POST'])
def submit_practice():
    """
    提交练习答案并评估接口

    Expected JSON input:
        {
            "user_id": "student_001",
            "answers": [
                {
                    "question_id": "q_2_...",
                    "node_id": 2,
                    "question_text": "...",
                    "student_answer": "..."
                }
            ]
        }

    Returns:
        {
            "results": [{"question_id": "q_2_...", "node_id": 2, "node_name": "...",
                         "score": 4, "comment": "...",
                         "mastery_before": 0.5, "mastery_after": 0.75}, ...],
            "summary": {"total": 1, "average_score": 4.0,
                        "score_breakdown": {"5": 0, "4": 1, "3": 0, "2": 0, "1": 0}}
        }
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        if 'answers' not in data or not isinstance(data['answers'], list):
            return jsonify({'error': '缺少answers字段或格式不正确'}), 400

        user_id = data['user_id']
        answers = data['answers']

        if len(answers) == 0:
            return jsonify({'error': 'answers不能为空'}), 400

        results = []
        score_dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        total_score = 0
        scored_count = 0

        for ans in answers:
            question_id = ans.get('question_id', '')
            node_id = ans.get('node_id')
            question_text = ans.get('question_text', '')
            student_answer = ans.get('student_answer', '')

            if node_id is None:
                results.append({
                    'question_id': question_id,
                    'error': '缺少node_id'
                })
                continue

            # 获取知识点名称
            node = database.get_node(node_id)
            node_name = node['name'] if node else f"知识点{node_id}"

            # 记录评估前的掌握度
            mastery_before = database.get_mastery(user_id, node_id)

            # 调用LLM评估
            try:
                score, comment = llm_api.evaluate_practice_answer(
                    node_name, question_text, student_answer
                )
            except Exception as e:
                results.append({
                    'question_id': question_id,
                    'node_id': node_id,
                    'node_name': node_name,
                    'score': None,
                    'comment': f'评估失败: {str(e)}',
                    'mastery_before': round(mastery_before, 2),
                    'mastery_after': round(mastery_before, 2)
                })
                continue

            # 将评分映射为掌握度并更新
            mastery_value = (score - 1) / 4.0
            delta = mastery_value - mastery_before
            new_mastery = database.update_mastery(user_id, node_id, delta=delta)

            score_dist[score] = score_dist.get(score, 0) + 1
            total_score += score
            scored_count += 1

            results.append({
                'question_id': question_id,
                'node_id': node_id,
                'node_name': node_name,
                'score': score,
                'comment': comment,
                'mastery_before': round(mastery_before, 2),
                'mastery_after': round(new_mastery, 2)
            })

        avg_score = round(total_score / scored_count, 1) if scored_count > 0 else 0

        response_data = {
            'results': results,
            'summary': {
                'total': len(results),
                'average_score': avg_score,
                'score_breakdown': score_dist
            }
        }

        # Save practice session to history
        try:
            target_nodes = list(set(a['node_id'] for a in answers if a.get('node_id') is not None))
            database.save_practice_session(user_id, target_nodes, answers, response_data)
        except Exception as e:
            print(f"保存练习记录失败（不影响提交结果）: {e}")

        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': f'提交练习答案时出错: {str(e)}'}), 500


@app.route('/api/stage-map', methods=['GET'])
def get_stage_map():
    """
    获取闯关地图：计算每个知识点的层级、解锁状态和掌握度。

    Expected query params:
        user_id: 用户ID

    Returns:
        {
            "layers": [{"layer": 0, "nodes": [{...}]}, ...],
            "prerequisites": [{"from": 1, "to": 2}, ...],
            "summary": {"total": 23, "cleared": 5, "unlocked": 3, "locked": 15}
        }
    """
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少user_id参数'}), 400

        layers_list, prereqs_list, summary = recommend.compute_stage_map(user_id)
        return jsonify({
            'layers': layers_list,
            'prerequisites': prereqs_list,
            'summary': summary,
        })

    except Exception as e:
        return jsonify({'error': f'获取闯关地图时出错: {str(e)}'}), 500


@app.route('/api/practice-history', methods=['GET'])
def get_practice_history():
    """
    获取用户的练习历史记录

    Expected query params:
        user_id: 用户ID
        limit: 返回记录数（可选，默认20）

    Returns:
        {"sessions": [...]}
    """
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少user_id参数'}), 400

        limit = request.args.get('limit', 20, type=int)
        sessions = database.get_practice_history(user_id, limit)
        return jsonify({'sessions': sessions})

    except Exception as e:
        return jsonify({'error': f'查询练习历史时出错: {str(e)}'}), 500


@app.route('/api/reset_mastery', methods=['POST'])
def reset_mastery():
    """
    重置当前用户的掌握度（所有知识点归零）

    Expected JSON input:
        {
            "user_id": "student_001"
        }

    Returns:
        {"message": "掌握度已重置"}
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        user_id = data['user_id']
        database.reset_user_mastery(user_id)

        return jsonify({'message': f'用户 {user_id} 的掌握度已重置'})

    except Exception as e:
        return jsonify({'error': f'重置掌握度时出错: {str(e)}'}), 500


@app.route('/api/reset', methods=['POST'])
def reset_all():
    """
    恢复原始配置：重置整个数据库（删除所有表并从CSV重新导入）

    Returns:
        {"message": "数据库已恢复为原始配置"}
    """
    try:
        database.reset_database()
        return jsonify({'message': '数据库已恢复为原始配置，所有用户掌握度已清除'})

    except Exception as e:
        return jsonify({'error': f'重置数据库时出错: {str(e)}'}), 500


# ===== Admin API =====

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Authenticate with admin credentials. Returns a Bearer token on success."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少请求体'}), 400

        username = data.get('username', '')
        password = data.get('password', '')

        if not username or not password:
            return jsonify({'error': '请输入管理员用户名和密码'}), 400

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            token = secrets.token_hex(32)
            _admin_tokens.add(token)
            return jsonify({'token': token})

        return jsonify({'error': '管理员用户名或密码错误'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    """Return all users with mastery stats."""
    try:
        users = database.get_all_users()
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
@_require_admin
def admin_delete_user(user_id):
    """Delete all data for a user. Requires admin token."""
    try:
        database.delete_user_data(user_id)
        return jsonify({'message': f'用户 {user_id} 的数据已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recommend-v2', methods=['POST'])
def get_recommendation_v2():
    """
    Advanced recommendation endpoint using path planner with 5 action types.

    Expected JSON input:
        {"user_id": "student_001"}

    Returns:
        {
            "recommendations": [{"action_type","target_dim","target_dim_name",
                                 "cost","reward","score","explanation","affected_dims"}, ...],
            "momentum": 0.0,
            "user_state_summary": {"dim_count": 106, "weak_dims": 12, "avg_mastery": 0.45}
        }
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        user_id = data['user_id']

        from path_planner import PathPlanner
        planner = PathPlanner(user_id)
        recommendations = planner.recommend()
        summary = planner.get_user_state_summary()

        return jsonify({
            'recommendations': [
                {
                    'action_type': a.action_type,
                    'target_dim': a.target_dim,
                    'target_dim_name': a.target_dim_name,
                    'cost': a.cost,
                    'reward': a.reward,
                    'score': a.score,
                    'explanation': a.explanation,
                    'affected_dims': a.affected_dims,
                }
                for a in recommendations
            ],
            'momentum': summary['momentum'],
            'user_state_summary': {
                'dim_count': summary['dim_count'],
                'weak_dims': summary['weak_dims'],
                'avg_mastery': summary['avg_mastery'],
            },
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'推荐引擎出错: {str(e)}'}), 500


@app.route('/api/submit-practice-v2', methods=['POST'])
def submit_practice_v2():
    """
    提交练习答案并评估接口（v2: 包含补偿事件检测）

    Expected JSON input:
        {
            "user_id": "student_001",
            "answers": [{"question_id": "...", "node_id": 2,
                         "question_text": "...", "student_answer": "..."}]
        }

    Returns:
        {
            "results": [...],
            "summary": {...},
            "compensation_events": [{"level": "L1"/"L2"/"L3"/"L4", ...}],
            "momentum": 0.15
        }
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': '缺少user_id字段'}), 400

        if 'answers' not in data or not isinstance(data['answers'], list):
            return jsonify({'error': '缺少answers字段或格式不正确'}), 400

        user_id = data['user_id']
        answers = data['answers']

        if len(answers) == 0:
            return jsonify({'error': 'answers不能为空'}), 400

        results = []
        score_dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        total_score = 0
        scored_count = 0
        compensation_events = []

        for ans in answers:
            question_id = ans.get('question_id', '')
            node_id = ans.get('node_id')
            question_text = ans.get('question_text', '')
            student_answer = ans.get('student_answer', '')

            if node_id is None:
                results.append({'question_id': question_id, 'error': '缺少node_id'})
                continue

            node = database.get_node(node_id)
            node_name = node['name'] if node else f"知识点{node_id}"

            # Snapshot before update
            mastery_before = database.get_mastery(user_id, node_id)

            try:
                score, comment = llm_api.evaluate_practice_answer(
                    node_name, question_text, student_answer
                )
            except Exception as e:
                results.append({
                    'question_id': question_id, 'node_id': node_id,
                    'node_name': node_name, 'score': None,
                    'comment': f'评估失败: {str(e)}',
                    'mastery_before': round(mastery_before, 2),
                    'mastery_after': round(mastery_before, 2),
                })
                continue

            mastery_value = (score - 1) / 4.0
            delta = mastery_value - mastery_before
            new_mastery = database.update_mastery(user_id, node_id, delta=delta)

            score_dist[score] = score_dist.get(score, 0) + 1
            total_score += score
            scored_count += 1

            # L1: per-question delta
            node_info = database.get_node(node_id)
            compensation_events.append({
                "level": "L1",
                "node_id": node_id,
                "node_name": node_name,
                "description": f"练习反馈: {node_name} mastery变化 {delta:+.3f}",
                "delta": round(delta, 3),
            })

            # L2: threshold crossing
            for t in [0.5, 0.7]:
                if mastery_before < t <= new_mastery:
                    compensation_events.append({
                        "level": "L2",
                        "node_id": node_id,
                        "node_name": node_name,
                        "description": f"阈值突破: {node_name} mastery 跨越 {t}",
                        "threshold": t,
                        "before": round(mastery_before, 3),
                        "after": round(new_mastery, 3),
                    })

            # L4: bottleneck breakthrough
            if mastery_before < 0.3 and new_mastery >= 0.5:
                compensation_events.append({
                    "level": "L4",
                    "node_id": node_id,
                    "node_name": node_name,
                    "description": f"瓶颈突破: {node_name} 从薄弱跃升至掌握",
                    "before": round(mastery_before, 3),
                    "after": round(new_mastery, 3),
                })

            results.append({
                'question_id': question_id, 'node_id': node_id,
                'node_name': node_name, 'score': score, 'comment': comment,
                'mastery_before': round(mastery_before, 2),
                'mastery_after': round(new_mastery, 2),
            })

        avg_score = round(total_score / scored_count, 1) if scored_count > 0 else 0

        # Update momentum based on average outcome
        if scored_count > 0:
            if avg_score >= 4.0:
                outcome_val = 0.15
            elif avg_score >= 3.0:
                outcome_val = 0.05
            elif avg_score >= 2.0:
                outcome_val = -0.1
            else:
                outcome_val = -0.3
            new_momentum = database.update_momentum_db(user_id, outcome_val)
        else:
            new_momentum = database.get_user_meta(user_id).get('momentum', 0.0)

        response_data = {
            'results': results,
            'summary': {
                'total': len(results),
                'average_score': avg_score,
                'score_breakdown': score_dist,
            },
            'compensation_events': compensation_events,
            'momentum': round(new_momentum, 3),
        }

        # Save practice session
        try:
            target_nodes = list(set(a['node_id'] for a in answers if a.get('node_id') is not None))
            database.save_practice_session(user_id, target_nodes, answers, response_data)
        except Exception as e:
            print(f"保存练习记录失败（不影响提交结果）: {e}")

        return jsonify(response_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'提交练习答案时出错: {str(e)}'}), 500


@app.route('/api/dim-mastery', methods=['GET'])
def get_dim_mastery():
    """Returns all dim-level mastery data."""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'missing user_id'}), 400
    dims = database.get_user_dim_mastery_all(user_id)
    nodes = database.get_user_node_mastery_derived_all(user_id)

    avg_mastery = sum(d['mastery'] for d in dims) / len(dims) if dims else 0.0
    weak_dims = [d for d in dims if d['mastery'] < 0.5]

    return jsonify({
        'dimensions': dims,
        'nodes': nodes,
        'summary': {
            'dim_count': len(dims),
            'node_count': len(nodes),
            'avg_mastery': round(avg_mastery, 4),
            'weak_count': len(weak_dims)
        }
    })


@app.route('/api/problem-for-dim', methods=['GET'])
def get_problem_for_dim():
    """Returns a problem for a given dimension."""
    dim_id = request.args.get('dim_id')
    if not dim_id:
        return jsonify({'error': 'missing dim_id'}), 400

    import json as _json
    import os as _os
    problems_path = _os.path.join(_os.path.dirname(__file__), 'data', 'problems.json')
    with open(problems_path, 'r', encoding='utf-8') as f:
        problems = _json.load(f)

    matching = []
    for p in problems:
        for step in p.get('steps', []):
            if step.get('dim_id') == dim_id:
                matching.append(p)
                break

    if not matching:
        return jsonify({'error': f'No problem found for dim_id: {dim_id}'}), 404

    dim = database.get_dimension(dim_id)
    dim_name = dim['name'] if dim else dim_id

    matching.sort(key=lambda p: abs(p.get('difficulty', 3) - 2.5))
    problem = matching[0]

    steps_with_choices = []
    for step in problem.get('steps', []):
        correct_text = step.get('text', '')
        wrong_choices = [ep.get('desc', '') for ep in step.get('error_patterns', [])]
        choices = [correct_text] + wrong_choices[:3]

        generic_wrong = ['跳过这一步直接算结果', '用其他不相关的方法', '不确定，随便试试']
        while len(choices) < 4:
            for g in generic_wrong:
                if g not in choices and len(choices) < 4:
                    choices.append(g)

        steps_with_choices.append({
            'id': step.get('id', ''),
            'text': step.get('text', ''),
            'choices': choices,
            'correct': 0
        })

    return jsonify({
        'problem': {
            'id': problem.get('id', ''),
            'text': problem.get('text', ''),
            'steps': steps_with_choices
        },
        'dim_id': dim_id,
        'dim_name': dim_name
    })


if __name__ == '__main__':
    # 在启动应用前初始化数据库
    print("正在初始化数据库...")
    database.init_db()
    database.ensure_practice_sessions_table()
    database.run_all_migrations()

    # 启动Flask应用
    print("启动Flask应用在 http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
