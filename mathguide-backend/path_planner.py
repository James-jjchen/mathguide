# -*- coding: utf-8 -*-
"""DB-backed path planner with 5 candidate action types and cost/reward scoring."""
import json
import os
from dataclasses import dataclass, field
from typing import Optional

import database

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


@dataclass
class CandidateAction:
    action_type: str      # "bottleneck" | "unlock" | "transfer" | "discovery" | "recovery"
    target_dim: str
    target_dim_name: str
    cost: float
    reward: float
    score: float          # reward / cost
    explanation: str      # Chinese text
    affected_dims: list = field(default_factory=list)


class PathPlanner:
    """Recommend next actions by scoring 5 candidate types against DB state."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        graph_path = os.path.join(DATA_DIR, "skill_graph.json")
        with open(graph_path, "r", encoding="utf-8") as f:
            self.graph_data = json.load(f)
        self.dims = self.graph_data.get("dimensions", {})
        self.nodes = self.graph_data.get("nodes", {})
        self.edges = self.graph_data.get("edges", [])

        # Build lookup: dim_id -> node_id
        self._dim_to_node = {}
        for nid, node in self.nodes.items():
            for d in node.get("dimensions", []):
                self._dim_to_node[d] = nid

        # Build outgoing edge index
        self._edges_by_from = {}
        for e in self.edges:
            self._edges_by_from.setdefault(e["from_dim"], []).append(e)

        # Build incoming edge index
        self._edges_by_to = {}
        for e in self.edges:
            self._edges_by_to.setdefault(e["to_dim"], []).append(e)

        # Build node prereq index (node_id -> {prereq_node_id: weight})
        self._node_prereqs = {}
        for nid, node in self.nodes.items():
            self._node_prereqs[nid] = node.get("prerequisites", {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(self) -> list:
        """Top-3 actions sorted by score desc."""
        state = self._get_user_state()
        candidates = []
        candidates += self._bottleneck_attack(state)
        candidates += self._unlock_nudge(state)
        candidates += self._transfer_opportunity(state)
        candidates += self._momentum_recovery(state)
        candidates += self._discovery(state)
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:3]

    # ------------------------------------------------------------------
    # User state
    # ------------------------------------------------------------------

    def _get_user_state(self) -> dict:
        """Load dim-level mastery, confidence, stuck_count, and momentum from DB."""
        dim_state = database.get_all_user_dim_state(self.user_id)
        meta = database.get_user_meta(self.user_id)
        if not dim_state:
            # Initialize if empty
            for dim_id in self.dims:
                dim_state[dim_id] = {"mastery": 0.0, "confidence": 0.0, "stuck_count": 0}
        return {
            "dims": dim_state,
            "momentum": meta.get("momentum", 0.0),
        }

    # ------------------------------------------------------------------
    # Action generators
    # ------------------------------------------------------------------

    def _bottleneck_attack(self, state: dict) -> list:
        """Dims with mastery < 0.5 OR (mastery < 0.6 AND confidence < 5.0)."""
        dims_state = state["dims"]
        candidates = []
        for dim_id, ds in dims_state.items():
            m = ds["mastery"]
            c = ds["confidence"]
            if m < 0.5 or (m < 0.6 and c < 5.0):
                dim_info = self.dims.get(dim_id, {})
                cost = self._compute_cost(dim_id, ds, state["momentum"])
                reward = self._compute_reward(dim_id, ds, "bottleneck")
                candidates.append(CandidateAction(
                    action_type="bottleneck",
                    target_dim=dim_id,
                    target_dim_name=dim_info.get("name", dim_id),
                    cost=round(cost, 4),
                    reward=round(reward, 4),
                    score=round(reward / max(cost, 0.001), 4),
                    explanation=f"瓶颈突破: {dim_info.get('name', dim_id)} (掌握度 {m:.2f})",
                    affected_dims=self._get_affected_dims(dim_id),
                ))
        candidates.sort(key=lambda x: x.cost)
        return candidates[:3]

    def _unlock_nudge(self, state: dict) -> list:
        """Dims where ALL prereq dims have mastery >= 0.45 AND dim mastery < 0.45."""
        dims_state = state["dims"]
        candidates = []
        for dim_id, ds in dims_state.items():
            if ds["mastery"] >= 0.45:
                continue
            if not self._all_prereqs_ready(dim_id, dims_state, 0.45):
                continue
            dim_info = self.dims.get(dim_id, {})
            candidates.append(CandidateAction(
                action_type="unlock",
                target_dim=dim_id,
                target_dim_name=dim_info.get("name", dim_id),
                cost=0.3,
                reward=0.5,
                score=round(0.5 / 0.3, 4),
                explanation=f"即将解锁: {dim_info.get('name', dim_id)} (前置已满足)",
                affected_dims=self._get_affected_dims(dim_id),
            ))
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:2]

    def _transfer_opportunity(self, state: dict) -> list:
        """Dims with mastery >= 0.6 that have outgoing edges to dims with mastery < 0.5."""
        dims_state = state["dims"]
        candidates = []
        seen = set()
        for from_dim, ds in dims_state.items():
            if ds["mastery"] < 0.6:
                continue
            for edge in self._edges_by_from.get(from_dim, []):
                to_dim = edge["to_dim"]
                if to_dim not in dims_state:
                    continue
                target_m = dims_state[to_dim]["mastery"]
                if target_m >= 0.5:
                    continue
                if to_dim in seen:
                    continue
                seen.add(to_dim)
                transfer_gain = edge.get("transfer_gain", 0.0)
                cog_dist = edge.get("cognitive_distance", 3)
                cost = cog_dist * (1.0 - transfer_gain)
                reward = min(transfer_gain * 0.5, 0.3)
                dim_info = self.dims.get(to_dim, {})
                from_info = self.dims.get(from_dim, {})
                candidates.append(CandidateAction(
                    action_type="transfer",
                    target_dim=to_dim,
                    target_dim_name=dim_info.get("name", to_dim),
                    cost=round(cost, 4),
                    reward=round(reward, 4),
                    score=round(reward / max(cost, 0.001), 4),
                    explanation=f"转移学习: {from_info.get('name', from_dim)}→{dim_info.get('name', to_dim)}",
                    affected_dims=[to_dim],
                ))
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:2]

    def _momentum_recovery(self, state: dict) -> list:
        """Only when momentum < -0.3. Find easiest dims (difficulty=1, mastery<0.3)."""
        if state["momentum"] >= -0.3:
            return []
        dims_state = state["dims"]
        candidates = []
        for dim_id, ds in dims_state.items():
            dim_info = self.dims.get(dim_id, {})
            if dim_info.get("difficulty", 99) != 1:
                continue
            if ds["mastery"] >= 0.3:
                continue
            cost = self._compute_cost(dim_id, ds, state["momentum"])
            reward = 0.15
            candidates.append(CandidateAction(
                action_type="recovery",
                target_dim=dim_id,
                target_dim_name=dim_info.get("name", dim_id),
                cost=round(cost, 4),
                reward=reward,
                score=round(reward / max(cost, 0.001), 4),
                explanation=f"动量恢复: {dim_info.get('name', dim_id)} (低难度，快速成功)",
                affected_dims=[dim_id],
            ))
        candidates.sort(key=lambda x: x.cost)
        return candidates[:2]

    def _discovery(self, state: dict) -> list:
        """Stub: suggest dims with difficulty <= 2 that haven't been attempted."""
        dims_state = state["dims"]
        candidates = []
        for dim_id, ds in dims_state.items():
            if ds["confidence"] > 2.0:
                continue
            dim_info = self.dims.get(dim_id, {})
            if dim_info.get("difficulty", 99) > 2:
                continue
            candidates.append(CandidateAction(
                action_type="discovery",
                target_dim=dim_id,
                target_dim_name=dim_info.get("name", dim_id),
                cost=0.5,
                reward=0.15,
                score=0.3,
                explanation=f"探索新领域: {dim_info.get('name', dim_id)}",
                affected_dims=[dim_id],
            ))
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:1]

    # ------------------------------------------------------------------
    # Cost / Reward formulas
    # ------------------------------------------------------------------

    def _compute_cost(self, dim_id: str, ds: dict, momentum: float) -> float:
        dim_info = self.dims.get(dim_id, {})
        difficulty = dim_info.get("difficulty", 1)
        mastery = ds["mastery"]
        confidence = ds["confidence"]
        stuck = ds.get("stuck_count", 0)

        cognitive_cost = 0.5 * difficulty
        gap_cost = 0.3 * max(0.0, 0.7 - mastery)
        stuck_penalty = 0.2 * min(stuck * 0.5, 2.0)

        if momentum < -0.3:
            momentum_mod = 1.0 + abs(momentum)
        elif momentum > 0.5:
            momentum_mod = 1.0 - momentum * 0.3
        else:
            momentum_mod = 1.0

        conf_discount = 0.7 if confidence < 3.0 else 1.0

        total = (cognitive_cost + gap_cost + stuck_penalty) * momentum_mod * conf_discount
        return max(0.01, total)

    def _compute_reward(self, dim_id: str, ds: dict, action_type: str) -> float:
        mastery = ds["mastery"]
        gap = max(0.0, 0.7 - mastery)

        # Base reward from closing the gap
        reward = gap * 0.5

        # Bonus for unlocking downstream nodes
        node_id = self._dim_to_node.get(dim_id)
        if node_id:
            unlock_bonus = 0.0
            for other_nid, prereqs in self._node_prereqs.items():
                if node_id in prereqs:
                    unlock_bonus += 0.1
            reward += min(unlock_bonus, 0.3)

        # Bonus from outgoing transfer edges
        for edge in self._edges_by_from.get(dim_id, []):
            reward += edge.get("transfer_gain", 0.0) * 0.15

        return max(0.01, round(reward, 4))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _all_prereqs_ready(self, dim_id: str, dims_state: dict, threshold: float) -> bool:
        """Check if all prerequisite dimensions for this dim's node are satisfied."""
        node_id = self._dim_to_node.get(dim_id)
        if not node_id:
            return True
        prereqs = self._node_prereqs.get(node_id, {})
        for prereq_node_id in prereqs:
            prereq_node = self.nodes.get(prereq_node_id, {})
            prereq_dims = prereq_node.get("dimensions", [])
            all_ready = True
            for pd in prereq_dims:
                if dims_state.get(pd, {}).get("mastery", 0.0) < threshold:
                    all_ready = False
                    break
            if not all_ready:
                return False
        return True

    def _get_affected_dims(self, dim_id: str) -> list:
        """Get dimensions that would be affected by improving this dim."""
        affected = [dim_id]
        for edge in self._edges_by_from.get(dim_id, []):
            if edge["to_dim"] not in affected:
                affected.append(edge["to_dim"])
        return affected

    def get_user_state_summary(self) -> dict:
        """Convenience wrapper around database.get_user_state_summary."""
        return database.get_user_state_summary(self.user_id)
