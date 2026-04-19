from flask import Flask, request, jsonify
from flask_cors import CORS
import database
import recommend
import llm_api

# 创建Flask应用实例
app = Flask(__name__)
# 启用CORS，允许前端跨域访问
CORS(app)

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
    初始化用户并设置已学章节

    Expected JSON input:
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
        chapter_ids = data.get('chapter_ids', [])

        if not isinstance(chapter_ids, list):
            return jsonify({'error': 'chapter_ids必须是数组'}), 400

        # 初始化用户掌握度表
        database.init_user_mastery(user_id)

        # 设置已学章节的初始掌握度
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

        # 调用LLM API获取回答（带知识边界限制）
        answer = llm_api.ask_math_question_with_boundary(question, learned_ids)

        # 如果提供了user_id，更新掌握度
        updated_mastery = {}
        if user_id:
            # 推断问题涉及的知识点
            involved_nodes = llm_api.infer_mastery_from_question(question, learned_ids)

            # 更新每个涉及知识点的掌握度
            for node_id in involved_nodes:
                new_mastery = database.update_mastery(user_id, node_id, delta=0.1)
                updated_mastery[str(node_id)] = new_mastery

        response = {'answer': answer}
        if updated_mastery:
            response['updated_mastery'] = updated_mastery

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': f'处理问题时出错: {str(e)}'}), 500

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


if __name__ == '__main__':
    # 在启动应用前初始化数据库
    print("正在初始化数据库...")
    database.init_db()

    # 启动Flask应用
    print("启动Flask应用在 http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
