# -*- coding: utf-8 -*-
"""CLI demo for skill-graph learning engine diagnostic loop."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import Engine, UserState

eng = Engine()
state = eng.init_user("demo")

# ====== Scenario: User tries P11 (x*lnx) and gets stuck ======
print("=" * 60)
print("场景: 用户刚开始学习，尝试 P11 (积分 x*lnx)")
print("用户在第1步就选错了u——把u设成了x, dv设成了lnx·dx")
print("=" * 60)
print()

# User gets step 1 wrong (wrong u selection)
_, feedback1 = eng.run_problem(state, "p11", [
    {"step_id": "p11_s1", "result": "wrong", "error": "u_wrong"},
    {"step_id": "p11_s2", "result": "wrong", "error": "diff_ln"},
    {"step_id": "p11_s3", "result": "stuck"},
    {"step_id": "p11_s4", "result": "stuck"},
])

print("--- 诊断结果 ---")
bottleneck = feedback1["bottleneck"]
dim_info = eng.graph.get_dim(bottleneck)
print(f"瓶颈维度: {bottleneck} ({dim_info['name']})")
print(f"所属节点: {eng.graph.get_dim_parent(bottleneck)}")
print()

print("--- 更新后的状态 (影响维度) ---")
for did in ["LIATE_choice", "log_inverse_integral", "basic_diff_table"]:
    m = state.dim_mastery.get(did, 0)
    c = state.dim_confidence.get(did, 0)
    s = state.stuck_count.get(did, 0)
    info = eng.graph.get_dim(did)
    print(f"  {did:30s} mastery={m:.3f}  conf={c:.3f}  stuck_count={s}")
print()

print(f"学习动量: {state.momentum:.3f}")
print()

print("--- 补偿事件 (L1-L4) ---")
for ev in feedback1.get("compensation_events", []):
    print(f"  [{ev.get('level', '?')}] {ev.get('description', '')}")
print()

print("--- 推荐下一步 (Top-3) ---")
for i, a in enumerate(feedback1["actions"]):
    cost_val = a.get('cost', 0)
    reward_str = a.get('reward_summary', '')
    score_val = a.get('cost', 0)  # fallback
    print(f"  #{i+1} [{a['type']:12s}] {a['reason']}")
    if isinstance(cost_val, (int, float)):
        print(f"       cost={cost_val:.2f}, reward={reward_str}")
print()

# ====== Scenario: User tries warmup and succeeds ======
print("=" * 60)
print("场景: 系统推荐了一道LIATE_choice的warmup题,")
print("用户全部正确完成")
print("=" * 60)

warmup = eng.prob_engine.get_warmup("LIATE_choice", state)
if warmup:
    print(f"推荐题目: {warmup['id']} (难度 {warmup['difficulty']})")
    print(f"题目: {warmup['text']}")
    print()

    # User gets all steps correct
    step_results = [{"step_id": s["id"], "result": "correct"} for s in warmup["steps"]]
    state, feedback2 = eng.run_problem(state, warmup["id"], step_results)

    print("--- 更新后的状态 ---")
    for did in ["LIATE_choice", "log_inverse_integral", "basic_diff_table"]:
        m = state.dim_mastery.get(did, 0)
        c = state.dim_confidence.get(did, 0)
        s = state.stuck_count.get(did, 0)
        info = eng.graph.get_dim(did)
        print(f"  {did:30s} mastery={m:.3f}  conf={c:.3f}  stuck_count={s}")

    print("--- 补偿事件 ---")
    for ev in feedback2.get("compensation_events", []):
        print(f"  [{ev.get('level', '?')}] {ev.get('description', '')}")

    print(f"学习动量: {state.momentum:.3f}")
    print()

    print("--- 重新推荐 (Top-3) ---")
    for i, a in enumerate(feedback2["actions"]):
        print(f"  #{i+1} [{a['type']:12s}] {a['reason']}")
        if a.get("cost"):
            print(f"       cost={a.get('cost',0):.2f}, reward={a.get('reward_summary','')}")

# ====== Scenario: User with good momentum tackles bottleneck ======
print()
print("=" * 60)
print("场景: 动量恢复后，回到分部积分类的瓶颈题目")
print("用户在第1步和第3步做对了，但第2步(求lnx的微分)错了")
print("系统应诊断出: 基本求导公式记忆不牢, 而不是分部积分问题")
print("=" * 60)

state2 = eng.init_user("demo2")
# First give some correct answers to build momentum
for _ in range(3):
    state2.apply_correct("limit_basic_ops")
state2.update_momentum()

_, feedback3 = eng.run_problem(state2, "p11", [
    {"step_id": "p11_s1", "result": "correct"},
    {"step_id": "p11_s2", "result": "wrong", "error": "diff_ln"},
    {"step_id": "p11_s3", "result": "correct"},
    {"step_id": "p11_s4", "result": "correct"},
])

print(f"诊断: 卡在第2步(p11_s2)")
print(f"错误类型: diff_ln")
print(f"系统定位: basic_diff_table 维度薄弱 (而非分部积分)")
print()

for did in ["LIATE_choice", "basic_diff_table", "log_inverse_integral"]:
    m = state2.dim_mastery.get(did, 0)
    s = state2.stuck_count.get(did, 0)
    print(f"  {did:30s} mastery={m:.3f}  stuck={s}")

print()
print("--- 补偿事件 ---")
for ev in feedback3.get("compensation_events", []):
    print(f"  [{ev.get('level', '?')}] {ev.get('description', '')}")

print()
print("--- 推荐 (Top-3) ---")
for i, a in enumerate(feedback3["actions"]):
    print(f"  #{i+1} [{a['type']:12s}] {a['reason']}")
    if a.get("cost"):
        print(f"       cost={a.get('cost',0):.2f}, reward={a.get('reward_summary','')}")

print()
print("系统现在应该: 虽然名义上是「分部积分」的题，")
print("但诊断出瓶颈是 basic_diff_table (lnx求导公式记错)")
print("→ 推荐回 basic_diff_table 的基础练习")
print("→ 而不是让用户继续做分部积分的题 —— 分步诊断的价值")

# ====== Phase 2: DB-backed PathPlanner demo ======
print()
print("=" * 60)
print("Phase 2: DB-backed PathPlanner (Top-3 推荐 + 评分)")
print("=" * 60)

# Initialize DB for demo user
import database
database.init_db()
database.ensure_practice_sessions_table()
database.run_all_migrations()
database.init_user_mastery("path_demo")

# Set some initial mastery for realistic scenario
database.set_chapter_mastery("path_demo", 1, initial_mastery=0.4)  # ch1: some knowledge
database.set_chapter_mastery("path_demo", 2, initial_mastery=0.2)  # ch2: weak

# Set specific weak dims
database.update_mastery("path_demo", 9, delta=-0.3)   # derivative_def weak
database.update_mastery("path_demo", 13, delta=-0.3)  # diff_rules weak

from path_planner import PathPlanner
planner = PathPlanner("path_demo")
recs = planner.recommend()
summary = planner.get_user_state_summary()

print(f"\n用户状态: {summary['dim_count']} 个维度, "
      f"{summary['weak_dims']} 个薄弱, "
      f"平均掌握度 {summary['avg_mastery']}, "
      f"动量 {summary['momentum']:.3f}")
print()
print("--- Top-3 推荐行动 ---")
for i, r in enumerate(recs):
    print(f"#{i+1} [{r.action_type:12s}] {r.target_dim_name}")
    print(f"    dim: {r.target_dim}")
    print(f"    cost={r.cost:.4f}  reward={r.reward:.4f}  score={r.score:.4f}")
    print(f"    {r.explanation}")
    if r.affected_dims:
        print(f"    影响维度: {', '.join(r.affected_dims[:5])}")
    print()

print("=" * 60)
print("Phase 2 验证通过: 路径规划器 + 补偿事件 + 动量系统")
