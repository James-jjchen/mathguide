import requests
from dotenv import load_dotenv
import os
from typing import Tuple, Optional, List, Dict, Any
import re
import json
import time
import database

load_dotenv()  # 加载 .env 文件

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-v4-pro"

def call_deepseek(messages: list, temperature: float = 0.7, max_tokens: int = 4096,
                  enable_thinking: bool = False) -> Dict[str, Any]:
    """
    调用DeepSeek大模型的基础函数

    Args:
        messages: 消息列表，格式为[{"role": "user", "content": "内容"}, ...]
        temperature: 温度参数，控制输出随机性 (0-2)，默认0.7
        max_tokens: 最大生成token数，默认4096
        enable_thinking: 是否启用思考模式，默认False

    Returns:
        字典，包含:
        - content: 模型返回的文本内容
        - reasoning_content: 推理过程内容（如果启用thinking）
        - error: 错误信息（如果调用失败）
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

        # 显式控制 thinking 模式（v4-pro 默认启用，需显式关闭）
        payload["extra_body"] = {"thinking": {"type": "enabled" if enable_thinking else "disabled"}}

        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]["message"]
                return {
                    "content": choice.get("content", ""),
                    "reasoning_content": choice.get("reasoning_content", ""),
                    "success": True
                }
            else:
                return {
                    "content": "",
                    "reasoning_content": "",
                    "error": "API返回结果中没有找到回答内容",
                    "success": False
                }
        else:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json()
                if "error" in error_detail:
                    error_msg += f": {error_detail['error'].get('message', 'Unknown error')}"
            except:
                pass
            return {
                "content": "",
                "reasoning_content": "",
                "error": f"API请求失败: {error_msg}",
                "success": False
            }

    except requests.exceptions.Timeout:
        return {
            "content": "",
            "reasoning_content": "",
            "error": "请求超时，请检查网络连接或稍后重试",
            "success": False
        }
    except requests.exceptions.ConnectionError:
        return {
            "content": "",
            "reasoning_content": "",
            "error": "网络连接错误，请检查网络状态",
            "success": False
        }
    except requests.exceptions.RequestException as e:
        return {
            "content": "",
            "reasoning_content": "",
            "error": f"请求异常: {str(e)}",
            "success": False
        }
    except Exception as e:
        return {
            "content": "",
            "reasoning_content": "",
            "error": f"未知错误: {str(e)}",
            "success": False
        }

def call_deepseek_stream(messages: list, temperature: float = 0.7,
                         max_tokens: int = 2048):
    """
    流式调用DeepSeek API，逐块yield SSE格式的token

    Args:
        messages: 消息列表
        temperature: 温度参数
        max_tokens: 最大生成token数

    Yields:
        SSE格式字符串: "data: <json>\n\n"
    """
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "extra_body": {"thinking": {"type": "disabled"}}
    }

    try:
        response = requests.post(url, headers=headers, json=payload,
                                 stream=True, timeout=(10, 120))
        if response.status_code != 200:
            yield f"data: {json.dumps({'error': f'HTTP {response.status_code}'})}\n\n"
            return

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith('data: '):
                continue
            data_str = line[6:]
            if data_str == '[DONE]':
                yield 'data: [DONE]\n\n'
                break
            yield f"data: {data_str}\n\n"

    except requests.exceptions.Timeout:
        yield f"data: {json.dumps({'error': '请求超时'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


def ask_math_question_stream(question: str, learned_ids: Optional[List[int]] = None):
    """
    流式数学问答接口，逐token返回

    Args:
        question: 数学问题
        learned_ids: 学生已学知识点ID列表（可选）

    Yields:
        SSE格式字符串
    """
    if not question or not question.strip():
        yield f"data: {json.dumps({'error': '请输入有效的数学问题'})}\n\n"
        return

    system_prompt = """你是一位大学数学助教，用简洁易懂的方式讲解微积分。
1. 分步骤讲解，每步解释清楚
2. 使用LaTeX公式：行内 $...$，独立 $$...$$。严禁 \\(...\\) 或 \\[...\\]
3. 回答简洁通俗，避免过于专业的术语"""

    boundary_prompt = build_knowledge_boundary_prompt(learned_ids)
    if boundary_prompt:
        system_prompt += boundary_prompt

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    yield from call_deepseek_stream(messages, max_tokens=2048)


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

    # 构建紧凑知识边界提示
    names = "、".join(learned_names)
    boundary_text = f"\n\n【知识范围】该学生已学：{names}。请只用上述概念讲解。如需用到未学知识，先指出并建议先修。"

    return boundary_text


def ask_math_question_with_boundary(question: str, learned_ids: Optional[List[int]] = None,
                                    enable_thinking: bool = False) -> str:
    """
    针对数学问题的专用接口，根据学生已学知识点动态调整回答策略

    Args:
        question: 数学问题
        learned_ids: 学生已学知识点ID列表（可选）
        enable_thinking: 是否启用深度思考模式，默认False

    Returns:
        模型的回答内容，格式化为分步骤、通俗易懂的形式
    """
    if not question or not question.strip():
        return "请输入有效的数学问题"

    # 构建基础system prompt
    system_prompt = """你是一位大学数学助教，用简洁易懂的方式讲解微积分。
1. 分步骤讲解，每步解释清楚
2. 使用LaTeX公式：行内 $...$，独立 $$...$$。严禁 \\(...\\) 或 \\[...\\]
3. 回答简洁通俗，避免过于专业的术语"""

    # 添加知识边界约束
    boundary_prompt = build_knowledge_boundary_prompt(learned_ids)
    if boundary_prompt:
        system_prompt += boundary_prompt

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    result = call_deepseek(messages, max_tokens=2048, enable_thinking=enable_thinking)

    if result.get("success"):
        # 如果启用了thinking，可以选择在回答中包含推理过程
        reasoning = result.get("reasoning_content", "")
        content = result.get("content", "")

        # 这里可以根据需要决定是否展示推理过程
        # 目前只返回最终答案
        return content
    else:
        return result.get("error", "回答失败")

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

        # 检查是否调用成功
        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            print(f"API调用失败: {error_msg}")
            return 3, f"评估失败：{error_msg}"

        # 获取返回内容
        content = result.get("content", "")

        if not content:
            return 3, "评估失败：模型未返回内容"

        # 打印原始响应以便调试
        print(f"模型原始响应:\n{content}\n")

        # 使用正则表达式提取评分和评语
        score_match = re.search(r'评分[:：]?\s*(\d+)分?', content)
        comment_match = re.search(r'评语[:：]?\s*(.+)', content)

        score = int(score_match.group(1)) if score_match else 3
        comment = comment_match.group(1).strip() if comment_match else "评估失败：无法解析评语"

        # 确保评分在有效范围内
        score = max(1, min(5, score))

        return score, comment

    except Exception as e:
        print(f"解析诊断结果时出错: {e}")
        import traceback
        traceback.print_exc()
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

    result = call_deepseek(messages)

    if result.get("success"):
        return result.get("content", "生成失败")
    else:
        return f"生成失败：{result.get('error', '未知错误')}"


def generate_practice_questions(node_ids: List[int], count_per_node: int = 1) -> List[Dict[str, Any]]:
    """
    为指定知识点生成练习题

    Args:
        node_ids: 知识点ID列表
        count_per_node: 每个知识点生成的题目数量，默认1

    Returns:
        [{"id": "q_<node_id>_<idx>", "node_id": int, "node_name": str,
          "type": "conceptual"|"calculation", "question_text": str, "hint": str}, ...]
    """
    if not node_ids:
        return []

    # 获取节点信息
    nodes_info = []
    for nid in node_ids:
        node = database.get_node(nid)
        if node:
            nodes_info.append(node)

    if not nodes_info:
        return []

    nodes_desc = "\n".join(f"{n['id']}: {n['name']}（难度{n['difficulty']}）" for n in nodes_info)

    system_prompt = """你是一位大学数学课程设计师，需要为指定知识点生成练习题。
要求：
1. 题目应能检验学生对知识点的核心理解
2. 概念题和计算题各占一半（交替生成）
3. 使用LaTeX（$$包裹）表示数学公式
4. 题目简洁明了，不超过三句话
5. 每题可附带一个简短提示（hint），帮助学生思考
6. **不要包含答案或解答步骤**

请严格按照以下JSON数组格式返回，不要包含任何其他文字：
[{"node_id": 5, "type": "conceptual", "question_text": "...", "hint": "提示：...", "node_name": "无穷小与无穷大"}]"""

    user_prompt = f"""请为以下知识点生成练习题（每题{count_per_node}道）：

{nodes_desc}

请以JSON数组格式返回（只返回JSON，不要其他文字）："""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        result = call_deepseek(messages, temperature=0.5, max_tokens=2048)
        if not result.get("success"):
            print(f"生成练习题LLM调用失败: {result.get('error')}")
            return []

        content = result.get("content", "").strip()
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            questions = json.loads(json_match.group())
            # 为每道题生成唯一ID
            for i, q in enumerate(questions):
                ts = int(time.time() * 1000)
                q["id"] = f"q_{q.get('node_id', 0)}_{ts}_{i}"
                if "node_name" not in q:
                    node = database.get_node(q.get("node_id", 0))
                    q["node_name"] = node["name"] if node else ""
            return questions
        else:
            print(f"无法从LLM响应中解析JSON: {content[:200]}")
            return []
    except json.JSONDecodeError as e:
        print(f"练习题JSON解析失败: {e}")
        return []
    except Exception as e:
        print(f"生成练习题异常: {e}")
        return []


def evaluate_practice_answer(node_name: str, question_text: str,
                              student_answer: str) -> Tuple[int, str]:
    """
    评估学生对练习题的回答

    Args:
        node_name: 知识点名称
        question_text: 练习题内容
        student_answer: 学生的回答

    Returns:
        (score: 1-5, comment: str)
    """
    if not student_answer or not student_answer.strip():
        return 1, "未提供回答"

    system_prompt = """你是一位经验丰富的大学数学教师，正在评估学生的练习题回答。
请根据学生的回答，严格按照以下格式输出评估结果：
评分：X分
评语：...（一句话评语，指出优点和不足）

评分标准：
5分：完全正确，思路清晰，表述准确
4分：基本正确，有少量不准确之处
3分：部分正确，核心概念有理解但存在明显错误
2分：理解严重偏差，只有零星正确点
1分：完全错误或答非所问

要求：
- 评分必须是1-5之间的整数
- 评语要简洁明了
- 输出格式必须严格遵守上述要求"""

    user_prompt = f"""请评估学生对"{node_name}"相关练习题的回答。

题目：
{question_text}

学生回答：
{student_answer}

请给出你的评估："""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        result = call_deepseek(messages, temperature=0.3)
        if not result.get("success"):
            return 3, f"评估失败：{result.get('error', '未知错误')}"

        content = result.get("content", "")
        if not content:
            return 3, "评估失败：模型未返回内容"

        score_match = re.search(r'评分[:：]?\s*(\d+)分?', content)
        comment_match = re.search(r'评语[:：]?\s*(.+)', content)

        score = int(score_match.group(1)) if score_match else 3
        comment = comment_match.group(1).strip() if comment_match else "无法解析评语"
        score = max(1, min(5, score))

        return score, comment

    except Exception as e:
        print(f"评估练习题异常: {e}")
        return 3, "评估失败：无法解析模型响应"

CONFIDENCE_THRESHOLD = 0.3


def infer_nodes_from_question_llm(question: str) -> List[Dict[str, Any]]:
    """
    使用大模型推断问题涉及的知识点及置信度

    Args:
        question: 学生的问题

    Returns:
        [{"node_id": int, "node_name": str, "confidence": float}, ...]
        仅返回置信度 >= CONFIDENCE_THRESHOLD 的节点
    """
    if not question or not question.strip():
        return []

    all_nodes_text = database.get_all_nodes_text()

    system_prompt = """你是一位大学数学课程专家，擅长分析数学问题涉及的知识点。
请根据学生提出的问题，判断问题涉及哪些知识点（从下方列表中选出），并给出置信度(0.0-1.0)。
置信度表示该知识点与问题的相关程度：
- 1.0: 问题是直接关于该知识点的
- 0.5-0.9: 问题与该知识点高度相关
- 0.3-0.5: 问题可能用到该知识点
- <0.3: 不相关

请仅返回一个JSON数组，不要包含任何其他文字：
[{"node_id": 2, "node_name": "极限的ε-δ定义", "confidence": 0.95}, ...]"""

    user_prompt = f"""知识点列表（ID: 名称）：
{all_nodes_text}

学生问题：{question}

请以JSON数组格式返回涉及的知识点（只返回JSON，不要其他文字）："""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        result = call_deepseek(messages, temperature=0.1, max_tokens=512)
        if not result.get("success"):
            print(f"节点推断LLM调用失败: {result.get('error')}")
            return []

        content = result.get("content", "").strip()
        # 尝试提取JSON数组
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            nodes = json.loads(json_match.group())
            # 过滤低置信度并验证node_id
            filtered = []
            for n in nodes:
                nid = n.get("node_id")
                conf = n.get("confidence", 0)
                if isinstance(nid, int) and conf >= CONFIDENCE_THRESHOLD:
                    filtered.append({
                        "node_id": nid,
                        "name": n.get("node_name", ""),
                        "confidence": round(conf, 2)
                    })
            return filtered
        else:
            print(f"无法从LLM响应中解析JSON: {content[:200]}")
            return []
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        return []
    except Exception as e:
        print(f"节点推断异常: {e}")
        return []


def evaluate_question_quality(question: str) -> Tuple[int, str]:
    """
    评估学生提问的质量，返回评分(0-10)和理由。

    评分标准：
    - 8-10: 高质量问题，体现对微积分概念的深入思考或合理困惑
    - 5-7: 一般问题，有一定相关性但深度不足
    - 2-4: 低质量问题，概念混乱、表述不清或与微积分几乎无关
    - 0-1: 荒谬提问，明显不经过思考、完全无关或故意捣乱

    Args:
        question: 学生的问题文本

    Returns:
        (quality_score: int 0-10, reason: str)
    """
    if not question or not question.strip():
        return (0, "空问题")

    system_prompt = """你是一位大学数学教师，需要评估学生提问的质量。
请根据以下标准对学生的提问进行评分（0-10分）：

- 8-10分：高质量问题。问题清晰、有深度，体现对微积分概念的认真思考，或是合理的、有助于学习的困惑。
- 5-7分：一般问题。有一定相关性，但深度不足，或表述不够清晰。
- 2-4分：低质量问题。概念混乱、表述不清，或与微积分课程内容几乎无关。
- 0-1分：荒谬提问。明显不经过思考、完全无关的闲聊，或故意捣乱。

请仅返回以下JSON格式，不要包含任何其他文字：
{"score": 6, "reason": "简短理由（一句话）"}"""

    user_prompt = f"学生提问：{question}\n\n请评估这个提问的质量，返回JSON："

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        result = call_deepseek(messages, temperature=0.1, max_tokens=128)
        if not result.get("success"):
            print(f"问题质量评估LLM调用失败: {result.get('error')}")
            return (5, "评估失败，默认中性评分")

        content = result.get("content", "").strip()
        json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', content)
        if json_match:
            data = json.loads(json_match.group())
            score = int(data.get("score", 5))
            score = max(0, min(10, score))
            reason = data.get("reason", "")
            return (score, reason)
        else:
            print(f"无法从LLM响应中解析质量评分: {content[:200]}")
            return (5, "评分解析失败，默认中性评分")

    except Exception as e:
        print(f"问题质量评估异常: {e}")
        return (5, f"评估异常: {str(e)}")


if __name__ == "__main__":
    print("=== MathGuide LLM API 测试 ===\n")

    # 1. 数学问答测试
    print("1. 数学问答测试:")
    math_result = ask_math_question("什么是极限的ε-δ定义？请用通俗语言解释")
    print(f"回答:\n{math_result}\n")

    # 2. LLM节点推断测试
    print("2. LLM节点推断测试:")
    nodes = infer_nodes_from_question_llm("如何用导数定义求函数的导数？")
    for n in nodes:
        print(f"  - {n['node_id']}: {n['name']} (置信度: {n['confidence']})")
    print()

    # 3. 智能诊断测试
    print("3. 智能诊断测试:")
    score, comment = diagnose_mastery("导数定义", "导数就是函数的变化率")
    print(f"  评分: {score}分, 评语: {comment}\n")

    # 4. 练习题生成测试
    print("4. 练习题生成测试:")
    questions = generate_practice_questions([2, 3], count_per_node=1)
    for q in questions:
        print(f"  [{q['node_name']}] ({q['type']}) {q['question_text'][:60]}...")
    print()

    # 5. 练习评估测试
    if questions:
        print("5. 练习评估测试:")
        score, comment = evaluate_practice_answer(
            questions[0]['node_name'],
            questions[0]['question_text'],
            "根据ε-δ定义，对于任意ε>0，存在δ>0，使得当0<|x-a|<δ时，|f(x)-L|<ε"
        )
        print(f"  评分: {score}分, 评语: {comment}")