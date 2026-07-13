"""
Core modules for the skill-graph learning engine.
"""
import json, copy, os, math

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

class SkillGraph:
    def __init__(self, path=None):
        path = path or os.path.join(DATA_DIR, "skill_graph.json")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self.nodes = raw["nodes"]
        self.dims = raw["dimensions"]
        self.edges = raw["edges"]
        # Build index: dim_id -> mastering which node, weight in that node
        self._dim_to_node = {}
        for nid, node in self.nodes.items():
            for d in node["dimensions"]:
                self._dim_to_node[d] = nid
        # Build edge index
        self._edges_by_from = {}
        for e in self.edges:
            self._edges_by_from.setdefault(e["from_dim"], []).append(e)

    def get_node(self, nid):
        return self.nodes.get(nid)

    def get_dim(self, did):
        return self.dims.get(did)

    def get_dim_parent(self, did):
        return self._dim_to_node.get(did)

    def get_transfers(self, from_dim):
        return self._edges_by_from.get(from_dim, [])

    def get_prereq_score(self, node_id, state):
        node = self.nodes.get(node_id)
        if not node:
            return 1.0
        prereqs = node.get("prerequisites", {})
        if not prereqs:
            return 1.0
        scores = []
        for pid, weight in prereqs.items():
            nm = state.node_mastery.get(pid, 0)
            scores.append(nm * weight)
        return sum(scores) / sum(prereqs.values()) if prereqs else 1.0

    def is_unlocked(self, node_id, state, threshold=0.5):
        return self.get_prereq_score(node_id, state) >= threshold

    def get_reachable(self, state):
        reachable = []
        for nid, node in self.nodes.items():
            if self.is_unlocked(nid, state) and state.node_mastery.get(nid, 0) < 0.5:
                reachable.append(nid)
        return reachable


class UserState:
    def __init__(self, uid="test_user"):
        self.uid = uid
        self.node_mastery = {}   # nid -> float
        self.dim_mastery = {}    # dim_id -> float
        self.dim_confidence = {} # dim_id -> float (0-1)
        self.stuck_count = {}    # dim_id -> int
        self.momentum = 0.0
        self.recent_history = []  # list of (dim_id, delta, outcome)
        self.step_results = []    # per-step tracking for current problem

    def init_with_graph(self, graph: SkillGraph):
        for dim_id in graph.dims:
            self.dim_mastery[dim_id] = 0.0
            self.dim_confidence[dim_id] = 0.0
            self.stuck_count[dim_id] = 0
        for nid in graph.nodes:
            self.node_mastery[nid] = 0.0

    def apply_correct(self, dim_id):
        old = self.dim_mastery.get(dim_id, 0)
        conf = self.dim_confidence.get(dim_id, 0)
        # Low confidence → bigger update
        update = 0.15 * (1 - conf * 0.5)
        self.dim_mastery[dim_id] = min(1.0, old + update)
        self.dim_confidence[dim_id] = min(1.0, conf + 0.1)
        self.stuck_count[dim_id] = 0  # reset stuck on success
        self.recent_history.append((dim_id, update, "correct"))
        return update

    def apply_wrong(self, dim_id, error_type=None):
        old = self.dim_mastery.get(dim_id, 0)
        conf = self.dim_confidence.get(dim_id, 0)
        update = -0.1 * (1 - conf * 0.3)
        self.dim_mastery[dim_id] = max(0.0, old + update)
        self.dim_confidence[dim_id] = min(1.0, conf + 0.15)  # certainty in the negative
        self.stuck_count[dim_id] = self.stuck_count.get(dim_id, 0) + 1
        self.recent_history.append((dim_id, update, "wrong"))
        return update

    def apply_stuck(self, dim_id, error_type=None):
        old = self.dim_mastery.get(dim_id, 0)
        update = -0.2
        self.dim_mastery[dim_id] = max(0.0, old + update)
        self.dim_confidence[dim_id] = min(1.0, self.dim_confidence.get(dim_id, 0) + 0.2)
        self.stuck_count[dim_id] = self.stuck_count.get(dim_id, 0) + 2
        self.recent_history.append((dim_id, update, "stuck"))
        return update

    def propagate_transfer(self, graph: SkillGraph, source_dim, delta):
        transfers = graph.get_transfers(source_dim)
        for edge in transfers:
            target = edge["to_dim"]
            if target in self.dim_mastery:
                gain = delta * edge["transfer_gain"] * 0.5
                self.dim_mastery[target] = min(1.0, self.dim_mastery[target] + gain)
                self.recent_history.append((target, gain, f"transfer({source_dim})"))

    def update_momentum(self):
        recent = self.recent_history[-10:] if len(self.recent_history) > 10 else self.recent_history
        if not recent:
            self.momentum = 0.0
            return
        total = 0.0
        for _, delta, outcome in recent:
            if outcome == "correct":
                total += 0.15
            elif outcome == "wrong":
                total -= 0.15
            elif outcome == "stuck":
                total -= 0.3
            elif outcome.startswith("transfer"):
                total += 0.05
        self.momentum = max(-1.0, min(1.0, total / len(recent)))

    def recompute_node(self, graph: SkillGraph, node_id):
        node = graph.get_node(node_id)
        if not node:
            return
        dim_ids = node["dimensions"]
        if not dim_ids:
            return
        total = 0.0
        wsum = 0.0
        for did in dim_ids:
            dim = graph.get_dim(did)
            if dim:
                m = self.dim_mastery.get(did, 0)
                w = dim["node_weight"]
                total += m * w
                wsum += w
        if wsum > 0:
            self.node_mastery[node_id] = total / wsum

    def recompute_all(self, graph: SkillGraph):
        for nid in graph.nodes:
            self.recompute_node(graph, nid)

    def get_bottlenecks(self, n=3):
        """Return top-n lowest mastery dims that have been attempted."""
        candidates = [(did, m) for did, m in self.dim_mastery.items()
                      if m < 0.7 and self.stuck_count.get(did, 0) > 0]
        candidates.sort(key=lambda x: (x[1], -self.stuck_count.get(x[0], 0)))
        return candidates[:n]

    def get_pending_unlocks(self, graph: SkillGraph):
        """Node IDs that are almost unlocked."""
        result = []
        for nid, node in graph.nodes.items():
            score = graph.get_prereq_score(nid, self)
            if 0.45 <= score < 0.5:
                result.append((nid, score))
        return result


class ProblemEngine:
    def __init__(self, graph: SkillGraph, path=None):
        self.graph = graph
        path = path or os.path.join(DATA_DIR, "problems.json")
        with open(path, encoding="utf-8") as f:
            self.problems = json.load(f)
        # Index by dim
        self._by_dim = {}
        for p in self.problems:
            for s in p["steps"]:
                self._by_dim.setdefault(s["dim_id"], []).append(p["id"])

    def get_by_dim(self, dim_id):
        return self._by_dim.get(dim_id, [])

    def get_problem(self, pid):
        for p in self.problems:
            if p["id"] == pid:
                return p
        return None

    def get_warmup(self, dim_id, state=None):
        """Find easiest problem that exercises this dim."""
        pids = self._by_dim.get(dim_id, [])
        easiest = None
        for pid in pids:
            p = self.get_problem(pid)
            if p and (easiest is None or p["difficulty"] < easiest["difficulty"]):
                easiest = p
        return easiest

    def get_adaptive(self, dim_id, state):
        confidence = state.dim_confidence.get(dim_id, 0)
        mastery = state.dim_mastery.get(dim_id, 0)
        momentum = state.momentum
        pids = self._by_dim.get(dim_id, [])
        candidates = [self.get_problem(pid) for pid in pids if self.get_problem(pid)]
        if not candidates:
            return None
        # Filter by difficulty based on state
        target_diff = None
        if momentum < -0.5:
            target_diff = min(c.difficulty for c in candidates)
        elif mastery > 0.7:
            target_diff = max(c.difficulty for c in candidates)
        else:
            target_diff = math.floor(sum(c.difficulty for c in candidates) / len(candidates))
        best = min(candidates, key=lambda c: abs(c["difficulty"] - target_diff))
        return best


class PathPlanner:
    def __init__(self, graph: SkillGraph, problem_engine: ProblemEngine):
        self.graph = graph
        self.problems = problem_engine
        self.last_actions = []

    def plan(self, state: UserState, n=3):
        actions = []

        # Type 1: Bottleneck attack (highest priority)
        if state.momentum >= -0.3:
            for dim_id, mastery in state.get_bottlenecks(3):
                p = self.problems.get_warmup(dim_id, state)
                problem_id = p["id"] if p else None
                cost = self._cost(state, dim_id)
                reward = self._reward(state, dim_id)
                actions.append({
                    "type": "bottleneck",
                    "dim_id": dim_id,
                    "problem_id": problem_id,
                    "reason": f"瓶颈: {self.graph.get_dim(dim_id)['name']} (掌握度 {mastery:.2f})",
                    "cost": cost,
                    "reward_summary": reward,
                })

        # Type 2: Pending unlock
        for nid, score in state.get_pending_unlocks(self.graph):
            dims = self.graph.get_node(nid)["dimensions"]
            target_dim = dims[0] if dims else None
            p = self.problems.get_warmup(target_dim, state) if target_dim else None
            actions.append({
                "type": "unlock",
                "node_id": nid,
                "dim_id": target_dim,
                "problem_id": p["id"] if p else None,
                "reason": f"即将解锁: {self.graph.get_node(nid)['name']} (前置得分 {score:.2f})",
                "cost": 2.0,
                "reward_summary": f"解锁新概念 + 关联题解封",
            })

        # Type 3: Transfer opportunity
        for dim_id, mastery in state.dim_mastery.items():
            if mastery > 0.6 and state.dim_confidence.get(dim_id, 0) > 0.5:
                for e in self.graph.get_transfers(dim_id):
                    target_m = state.dim_mastery.get(e["to_dim"], 0)
                    if target_m < 0.4 and e["edge_type"] == "transfer":
                        p = self.problems.get_warmup(e["to_dim"], state)
                        actions.append({
                            "type": "transfer",
                            "from_dim": dim_id,
                            "to_dim": e["to_dim"],
                            "problem_id": p["id"] if p else None,
                            "reason": f"转移学习: {self.graph.get_dim(dim_id)['name']}→{self.graph.get_dim(e['to_dim'])['name']}",
                            "cost": 1.5,
                            "reward_summary": f"关联维度提升",
                        })

        # Sort by: low momentum → prefer low cost; high momentum → prefer bottleneck
        if state.momentum < -0.3:
            actions.sort(key=lambda a: a["cost"])
        else:
            actions.sort(key=lambda a: (-1 if a["type"] == "bottleneck" else 0, a["cost"]))

        self.last_actions = actions[:n]
        return self.last_actions

    def _cost(self, state, dim_id):
        # Check prereq
        node_id = self.graph.get_dim_parent(dim_id)
        if node_id:
            if not self.graph.is_unlocked(node_id, state, 0.3):
                return 999
        gap = 1.0 - state.dim_mastery.get(dim_id, 0)
        stuck = state.stuck_count.get(dim_id, 0)
        stuck_penalty = min(stuck * 0.5, 2.0)
        cost = 0.5 * gap + 0.5 * stuck_penalty
        return cost

    def _reward(self, state, dim_id):
        gap = 1.0 - state.dim_mastery.get(dim_id, 0)
        locks = []
        for e in self.graph.get_transfers(dim_id):
            if e["edge_type"] == "transfer":
                locks.append(self.graph.get_dim(e["to_dim"])["name"])
        summary = f"掌握提升 ~{gap*0.3:.2f}"
        if locks:
            summary += f", 关联提升: {', '.join(locks[:2])}"
        return summary


class Engine:
    def __init__(self):
        self.graph = SkillGraph()
        self.prob_engine = ProblemEngine(self.graph)
        self.planner = PathPlanner(self.graph, self.prob_engine)

    def init_user(self, uid="demo"):
        state = UserState(uid)
        state.init_with_graph(self.graph)
        return state

    def run_problem(self, state: UserState, problem_id, step_results):
        problem = self.prob_engine.get_problem(problem_id)
        if not problem:
            return None, {"error": "Problem not found"}

        feedback = {"problem_id": problem_id, "steps": [], "bottleneck": None,
                    "compensation_events": []}
        steps_map = {s["id"]: s for s in problem["steps"]}

        # Snapshot before state for compensation detection
        before_dim = dict(state.dim_mastery)
        before_conf = dict(state.dim_confidence)
        before_momentum = state.momentum

        for sr in step_results:
            step = steps_map.get(sr["step_id"])
            if not step:
                continue
            dim_id = step["dim_id"]
            result = sr["result"]
            error = sr.get("error")

            # Capture per-step delta for L1
            before_step_m = state.dim_mastery.get(dim_id, 0)

            # 1) Update step's main dimension
            if result == "correct":
                d = state.apply_correct(dim_id)
                state.propagate_transfer(self.graph, dim_id, d)
            elif result == "wrong":
                state.apply_wrong(dim_id, error)
            elif result == "stuck":
                state.apply_stuck(dim_id, error)

            # L1: step-by-step mastery delta
            after_step_m = state.dim_mastery.get(dim_id, 0)
            step_delta = after_step_m - before_step_m
            state.step_results.append({
                "dim_id": dim_id, "result": result,
                "delta": round(step_delta, 4),
                "mastery_after": round(after_step_m, 4),
            })

            # 2) Error propagation: error_pattern -> root dim_affected
            if error and result in ("wrong", "stuck"):
                for ep in step.get("error_patterns", []):
                    if ep["pattern"] == error and ep["dim_affected"] != dim_id:
                        state.apply_wrong(ep["dim_affected"], error)

            state.recompute_node(self.graph, dim_id)
            feedback["steps"].append({
                "step_id": step["id"], "dim_id": dim_id, "result": result,
                "new_mastery": round(state.dim_mastery.get(dim_id, 0), 3),
            })

        # Find root cause bottleneck via error_pattern dim_affected
        bottleneck = None
        for sr in step_results:
            if sr["result"] in ("wrong", "stuck"):
                step = steps_map.get(sr["step_id"])
                if step:
                    error = sr.get("error")
                    if error:
                        for ep in step.get("error_patterns", []):
                            if ep["pattern"] == error:
                                bottleneck = ep["dim_affected"]
                                break
                    if not bottleneck:
                        bottleneck = step["dim_id"]
                    break

        state.update_momentum()
        state.recompute_all(self.graph)

        # Detect compensation events (L1-L4)
        compensation = self.detect_compensation_events(
            state, before_dim, before_conf, before_momentum,
            step_results, steps_map,
        )
        feedback["compensation_events"] = compensation

        actions = self.planner.plan(state)
        feedback["bottleneck"] = bottleneck
        feedback["momentum"] = round(state.momentum, 3)
        feedback["actions"] = actions
        return state, feedback

    def detect_compensation_events(self, state: UserState,
                                   before_dim: dict, before_conf: dict,
                                   before_momentum: float,
                                   step_results: list, steps_map: dict) -> list:
        """Detect L1-L4 compensation events from state change."""
        events = []

        # L1: per-step mastery deltas (from step_results tracking)
        for sr in state.step_results[-len(step_results):]:
            dim_id = sr["dim_id"]
            dim_info = self.graph.get_dim(dim_id)
            dim_name = dim_info["name"] if dim_info else dim_id
            events.append({
                "level": "L1",
                "dim_id": dim_id,
                "dim_name": dim_name,
                "description": f"步骤反馈: {dim_name} mastery变化 {sr['delta']:+.4f}",
                "delta": sr["delta"],
                "result": sr["result"],
            })

        # L2: threshold crossings (0.5 and 0.7)
        THRESHOLDS = [0.5, 0.7]
        for dim_id in before_dim:
            before_m = before_dim.get(dim_id, 0)
            after_m = state.dim_mastery.get(dim_id, 0)
            for t in THRESHOLDS:
                if before_m < t <= after_m:
                    dim_info = self.graph.get_dim(dim_id)
                    dim_name = dim_info["name"] if dim_info else dim_id
                    events.append({
                        "level": "L2",
                        "dim_id": dim_id,
                        "dim_name": dim_name,
                        "description": f"阈值突破: {dim_name} mastery 跨越 {t} ({before_m:.3f}→{after_m:.3f})",
                        "threshold": t,
                        "before": round(before_m, 4),
                        "after": round(after_m, 4),
                    })

        # L3: propagation effects (from recent_history transfer entries)
        for entry in state.recent_history[-len(step_results) * 3:]:
            dim_id, delta, outcome = entry
            if outcome.startswith("transfer"):
                dim_info = self.graph.get_dim(dim_id)
                dim_name = dim_info["name"] if dim_info else dim_id
                events.append({
                    "level": "L3",
                    "dim_id": dim_id,
                    "dim_name": dim_name,
                    "description": f"传播效应: {dim_name} 获得转移增益 +{delta:.4f}",
                    "delta": round(delta, 4),
                    "source": outcome,
                })

        # L4: bottleneck breakthrough (<0.3 → >= 0.5)
        for dim_id in before_dim:
            before_m = before_dim.get(dim_id, 0)
            after_m = state.dim_mastery.get(dim_id, 0)
            if before_m < 0.3 and after_m >= 0.5:
                dim_info = self.graph.get_dim(dim_id)
                dim_name = dim_info["name"] if dim_info else dim_id
                events.append({
                    "level": "L4",
                    "dim_id": dim_id,
                    "dim_name": dim_name,
                    "description": f"瓶颈突破: {dim_name} 从薄弱({before_m:.3f})跃升至掌握({after_m:.3f})",
                    "before": round(before_m, 4),
                    "after": round(after_m, 4),
                })

        # Momentum change
        if abs(state.momentum - before_momentum) > 0.01:
            events.append({
                "level": "momentum",
                "description": f"学习动量变化: {before_momentum:.3f}→{state.momentum:.3f}",
                "before": round(before_momentum, 3),
                "after": round(state.momentum, 3),
            })

        return events

    def get_full_user_state(self, state: UserState) -> dict:
        """Expose full user state dict for path planner integration."""
        return {
            "user_id": state.uid,
            "momentum": round(state.momentum, 3),
            "dim_mastery": {k: round(v, 4) for k, v in state.dim_mastery.items()},
            "dim_confidence": {k: round(v, 3) for k, v in state.dim_confidence.items()},
            "stuck_count": dict(state.stuck_count),
            "node_mastery": {k: round(v, 4) for k, v in state.node_mastery.items()},
        }

