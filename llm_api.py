import requests
from dotenv import load_dotenv
import os
from typing import Tuple, Optional, List
import re
import database

load_dotenv()  # 加载 .env 文件

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

def call_deepseek(messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> str:
    """
    调用DeepSeek大模型的基础函数

    Args:
        messages: 消息列表，格式为[{"role": "user", "content": "内容"}, ...]
        temperature: 温度参数，控制输出随机性 (0-2)，默认0.7
        max_tokens: 最大生成token数，默认1024

    Returns:
        模型返回的文本内容，如果调用失败则返回错误信息
    """
    try:
        url = f"{BASE_URL}/v1/chat/completions"

        headers = {
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                return "API返回结果中没有找到回答内容"
        else:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json()
                if "error" in error_detail:
                    error_msg += f": {error_detail['error'].get('message', 'Unknown error')}"
            except:
                pass
            return f"API请求失败: {error_msg}"

    except requests.exceptions.Timeout:
        return "请求超时，请检查网络连接或稍后重试"
    except requests.exceptions.ConnectionError:
        return "网络连接错误，请检查网络状态"
    except requests.exceptions.RequestException as e:
        return f"请求异常: {str(e)}"
    except Exception as e:
        return f"未知错误: {str(e)}"

def build_knowledge_boundary_prompt(learned_ids: Optional[List[int]] = None) -> str:
    """
    根据学生已学知识点构建知识边界提示词

    Args:
        learned_ids: 学生已学知识点ID列表

    Returns:
        知识边界约束文本，如果为空则返回空字符串
    """
    if not learned_ids or not isinstance(learned_ids, list) or len(learned_ids) == 0:
        return ""

    # 获取所有已学知识点的名称
    learned_names = []
    for node_id in learned_ids:
        try:
            node = database.get_node(node_id)
            if node:
                learned_names.append(node['name'])
            else:
                print(f"警告: 知识点ID {node_id} 不存在，已忽略")
        except Exception as e:
            print(f"警告: 查询知识点ID {node_id} 时出错: {e}")

    if not learned_names:
        return ""

    # 构建知识边界提示词
    boundary_text = "\n\n【重要约束：知识范围限制】\n"
    boundary_text += "该学生目前只学过以下知识点：\n"
    for i, name in enumerate(learned_names, 1):
        boundary_text += f"{i}. {name}\n"

    boundary_text += "\n请务必遵守以下规则：\n"
    boundary_text += "1. 只能使用上述已学知识点中的概念、定理和方法来解释问题\n"
    boundary_text += "2. 严禁使用学生未学的知识点（如导数、积分、泰勒公式等）进行解释\n"
    boundary_text += "3. 如果问题必须用到未学知识才能完整解答，请明确指出：'这个问题需要用到XXX知识，但你还未学习'\n"
    boundary_text += "4. 对于知识缺口，建议学生先学习相关前置知识点\n"
    boundary_text += "5. 尽量用已学知识的直观理解和类比来帮助学生建立认知桥梁"

    return boundary_text

def ask_math_question_with_boundary(question: str, learned_ids: Optional[List[int]] = None) -> str:
    """
    针对数学问题的专用接口，根据学生已学知识点动态调整回答策略

    Args:
        question: 数学问题
        learned_ids: 学生已学知识点ID列表（可选）

    Returns:
        模型的回答内容，格式化为分步骤、通俗易懂的形式
    """
    if not question or not question.strip():
        return "请输入有效的数学问题"

    # 构建基础system prompt
    system_prompt = """你是一位优秀的大学数学助教，擅长用简单易懂的方式向大一学生讲解数学概念。
请遵循以下原则回答问题：
1. 对于计算题：详细分解解题步骤，每步都要解释清楚
2. 对于概念题：先给出直观理解，再给出严格定义
3. 适当使用LaTeX公式（用$$包裹）来表示数学表达式
4. 可以举生活中的类比帮助理解
5. 最后给出总结性的结论
6. 回答应通俗易懂，避免过于专业的术语"""

    # 添加知识边界约束
    boundary_prompt = build_knowledge_boundary_prompt(learned_ids)
    if boundary_prompt:
        system_prompt += boundary_prompt

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    return call_deepseek(messages)

def ask_math_question(question: str) -> str:
    """
    针对数学问题的专用接口（兼容旧版本，不限制知识范围）

    Args:
        question: 数学问题

    Returns:
        模型的回答内容，格式化为分步骤、通俗易懂的形式
    """
    return ask_math_question_with_boundary(question, learned_ids=None)

def diagnose_mastery(knowledge_point: str, student_answer: str) -> Tuple[int, str]:
    """
    诊断学生对某个知识点的掌握程度

    Args:
        knowledge_point: 知识点名称（如"导数定义"）
        student_answer: 学生对该知识点的理解回答

    Returns:
        元组(score, comment)，其中score为1-5的整数评分，comment为评语
    """
    if not knowledge_point or not knowledge_point.strip():
        return 3, "知识点不能为空"

    if not student_answer or not student_answer.strip():
        return 3, "学生回答不能为空"

    # 构建诊断任务的system prompt
    system_prompt = """你是一位经验丰富的大学数学教师，正在评估学生对某个知识点的掌握程度。
请根据学生的回答，严格按照以下格式输出评估结果：
评分：X分
评语：...（一句话评语）

评分标准：
5分：完全正确，理解深刻，表述清晰
4分：基本正确，有少量不准确之处
3分：部分正确，核心概念有理解但存在明显错误
2分：理解严重偏差，只有零星正确点
1分：完全错误或答非所问

要求：
- 评分必须是1-5之间的整数
- 评语要简洁明了，指出主要优点和不足
- 输出格式必须严格遵守上述要求"""

    user_prompt = f"""请评估学生对"{knowledge_point}"这个知识点的掌握情况。

学生回答：
{student_answer}

请给出你的评估："""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        # 调用模型，降低temperature以提高输出稳定性
        result = call_deepseek(messages, temperature=0.3)

        # 解析返回结果
        if result.startswith("API") or result.startswith("请求"):
            # 如果是错误信息，直接返回默认值
            return 3, "评估失败：" + result

        # 使用正则表达式提取评分和评语
        score_match = re.search(r'评分[:：]?\s*(\d+)分?', result)
        comment_match = re.search(r'评语[:：]?\s*(.+)', result)

        score = int(score_match.group(1)) if score_match else 3
        comment = comment_match.group(1).strip() if comment_match else "评估失败"

        # 确保评分在有效范围内
        score = max(1, min(5, score))

        return score, comment

    except Exception as e:
        print(f"解析诊断结果时出错: {e}")
        return 3, "评估失败：无法解析模型响应"

def get_diagnostic_question(knowledge_point: str) -> str:
    """
    根据知识点生成一个简短的理解性诊断问题

    Args:
        knowledge_point: 知识点名称

    Returns:
        生成的理解性问题
    """
    if not knowledge_point or not knowledge_point.strip():
        return "请输入有效的知识点"

    system_prompt = """你是一位大学数学课程设计师，需要为每个知识点设计一个简短的理解性诊断问题。
要求：
1. 问题应该是概念性的，不是计算题
2. 问题应该能有效检验学生对该知识点的核心理解
3. 问题要简洁明了，不超过两句话
4. 不要包含答案"""

    user_prompt = f"""请为"{knowledge_point}"这个知识点设计一个理解性诊断问题。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return call_deepseek(messages)

if __name__ == "__main__":
    # 测试代码
    print("=== MathGuide LLM API 测试 ===\n")

    # 测试数学问答功能
    print("1. 数学问答测试:")
    math_result = ask_math_question("什么是极限的ε-δ定义？请用通俗语言解释")
    print(f"问题: 什么是极限的ε-δ定义？请用通俗语言解释")
    print(f"回答:\n{math_result}\n")

    # 测试智能诊断功能
    print("2. 智能诊断测试:")
    test_kp = "导数定义"
    test_answer = "导数就是函数的变化率，比如速度是位移的导数"
    score, comment = diagnose_mastery(test_kp, test_answer)
    print(f"知识点: {test_kp}")
    print(f"学生回答: {test_answer}")
    print(f"评分: {score}分")
    print(f"评语: {comment}\n")

    # 测试诊断问题生成功能
    print("3. 诊断问题生成测试:")
    question = get_diagnostic_question("积分基本定理")
    print(f"知识点: 积分基本定理")
    print(f"生成的问题: {question}")


def infer_mastery_from_question(question: str, learned_ids: Optional[List[int]] = None) -> List[int]:
    """
    简化版：根据问题中的关键词推断涉及的知识点ID
    （不依赖大模型，使用关键词匹配）

    Args:
        question: 学生的问题
        learned_ids: 学生已学知识点ID列表（可选，用于过滤）

    Returns:
        涉及的知识点ID列表
    """
    import database

    # 关键词到知识点ID的映射表（可根据实际数据扩展）
    keyword_to_node = {
        '函数': [1],
        '极限': [2, 3, 4, 5],
        'ε-δ': [2],
        'epsilon': [2],
        '连续': [6, 8],
        '间断': [7],
        '导数': [9, 10, 11, 12],
        '微分': [13, 14],
        '中值定理': [14],
        '罗尔': [14],
        '拉格朗日': [14],
        '泰勒': [15],
        '积分': [16, 17, 18, 19, 20, 21, 22, 23],
        '不定积分': [16, 17, 18, 19],
        '定积分': [20, 21, 22, 23],
        '换元': [17],
        '分部': [18],
    }

    # 将问题转为小写以便匹配
    question_lower = question.lower()

    # 匹配关键词
    matched_node_ids = set()
    for keyword, node_ids in keyword_to_node.items():
        if keyword.lower() in question_lower:
            matched_node_ids.update(node_ids)

    # 如果提供了learned_ids，只返回已学范围内的知识点
    if learned_ids:
        learned_set = set(learned_ids)
        matched_node_ids = matched_node_ids.intersection(learned_set)

    return list(matched_node_ids)


if __name__ == "__main__":
    # 测试代码
    print("=== MathGuide LLM API 测试 ===\n")

    # 测试数学问答功能
    print("1. 数学问答测试:")
    math_result = ask_math_question("什么是极限的ε-δ定义？请用通俗语言解释")
    print(f"问题: 什么是极限的ε-δ定义？请用通俗语言解释")
    print(f"回答:\n{math_result}\n")

    # 测试智能诊断功能
    print("2. 智能诊断测试:")
    test_kp = "导数定义"
    test_answer = "导数就是函数的变化率，比如速度是位移的导数"
    score, comment = diagnose_mastery(test_kp, test_answer)
    print(f"知识点: {test_kp}")
    print(f"学生回答: {test_answer}")
    print(f"评分: {score}分")
    print(f"评语: {comment}\n")

    # 测试诊断问题生成功能
    print("3. 诊断问题生成测试:")
    question = get_diagnostic_question("积分基本定理")
    print(f"知识点: 积分基本定理")
    print(f"生成的问题: {question}")