from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import (
    AgentTrajectory,
    Company,
    Insight,
    PageSnapshot,
    ResearchTask,
    RewardRecord,
    SourcePage,
    TrajectoryStep,
)


def create_research_task(
    db: Session,
    niche_id: int,
    name: str,
    prompt: str,
    evaluation_type: str,
    reward_definition: str | None,
    company_id: int | None = None,
) -> ResearchTask:
    if company_id is not None:
        company = db.get(Company, company_id)
        if company is None or company.niche_id != niche_id:
            raise ValueError(f"Company {company_id} not found in niche {niche_id}")

    task = ResearchTask(
        niche_id=niche_id,
        company_id=company_id,
        name=name.strip(),
        prompt=prompt.strip(),
        evaluation_type=evaluation_type,
        reward_definition=reward_definition,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, niche_id: int | None = None) -> list[ResearchTask]:
    query = select(ResearchTask).order_by(ResearchTask.created_at.desc())
    if niche_id is not None:
        query = query.where(ResearchTask.niche_id == niche_id)
    return db.scalars(query).all()


def create_baseline_trajectory(db: Session, task_id: int) -> AgentTrajectory:
    task = db.get(ResearchTask, task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")

    trajectory = AgentTrajectory(
        task_id=task.id,
        root_question=task.prompt,
        policy_name="basic-summary",
        status="completed",
    )
    db.add(trajectory)
    db.flush()

    evidence = _collect_snapshot_evidence(db, task.niche_id, task.company_id)
    steps = []
    for index, item in enumerate(evidence, start=1):
        steps.append(
            TrajectoryStep(
                trajectory_id=trajectory.id,
                snapshot_id=item["snapshot_id"],
                node_key=f"root.source_{index}",
                step_index=index,
                action_type="inspect_snapshot",
                action_input=item["url"],
                observation=item["summary"],
                branch_score=item["score"],
            )
        )
    db.add_all(steps)

    final_answer = _compose_answer(task.prompt, evidence)
    trajectory.final_answer = final_answer
    reward = _score_trajectory(evidence)
    trajectory.total_reward = reward["total"]
    db.flush()

    db.add(
        RewardRecord(
            trajectory_id=trajectory.id,
            reward_name="source_coverage",
            reward_value=reward["source_coverage"],
            reason=f"{reward['evidence_count']} evidence pages attached",
        )
    )
    db.add(
        RewardRecord(
            trajectory_id=trajectory.id,
            reward_name="freshness",
            reward_value=reward["freshness"],
            reason="Recent snapshots receive higher reward",
        )
    )
    db.add(
        RewardRecord(
            trajectory_id=trajectory.id,
            reward_name="source_diversity",
            reward_value=reward["diversity"],
            reason="Different page types improve branch coverage",
        )
    )
    db.add(
        Insight(
            niche_id=task.niche_id,
            company_id=task.company_id,
            scrape_run_id=evidence[0]["scrape_run_id"] if evidence else None,
            trajectory_id=trajectory.id,
            title=f"Summary: {task.name}",
            body=final_answer,
            source_url=evidence[0]["url"] if evidence else None,
        )
    )
    db.commit()
    db.refresh(trajectory)
    return trajectory


def create_tree_grpo_trajectory(db: Session, task_id: int) -> AgentTrajectory:
    task = db.get(ResearchTask, task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")

    trajectory = AgentTrajectory(
        task_id=task.id,
        root_question=task.prompt,
        policy_name="detailed-summary",
        status="completed",
    )
    db.add(trajectory)
    db.flush()

    evidence = _collect_snapshot_evidence(db, task.niche_id, task.company_id)
    search_result = _build_tree_search(task.prompt, evidence)
    step_id_by_key = _persist_tree_steps(db, trajectory.id, search_result["steps"])

    final_answer = _compose_tree_answer(task.prompt, search_result["rollouts"], evidence)
    reward = _score_tree_trajectory(
        search_result["selected_evidence"],
        search_result["rollouts"],
        achieved_depth=search_result["achieved_depth"],
    )
    trajectory.final_answer = final_answer
    trajectory.total_reward = reward["total"]
    db.flush()

    _record_tree_rewards(db, trajectory.id, reward, search_result["rollouts"], step_id_by_key)
    db.add(
        Insight(
            niche_id=task.niche_id,
            company_id=task.company_id,
            scrape_run_id=search_result["selected_evidence"][0]["scrape_run_id"]
            if search_result["selected_evidence"]
            else None,
            trajectory_id=trajectory.id,
            title=f"Detailed summary: {task.name}",
            body=final_answer,
            source_url=search_result["selected_evidence"][0]["url"]
            if search_result["selected_evidence"]
            else None,
        )
    )
    db.commit()
    db.refresh(trajectory)
    return trajectory


def list_trajectories(db: Session, task_id: int | None = None) -> list[AgentTrajectory]:
    query = (
        select(AgentTrajectory)
        .options(
            selectinload(AgentTrajectory.steps),
            selectinload(AgentTrajectory.rewards),
        )
        .order_by(AgentTrajectory.created_at.desc())
    )
    if task_id is not None:
        query = query.where(AgentTrajectory.task_id == task_id)
    return db.scalars(query).all()


def export_training_examples(db: Session, niche_id: int) -> list[dict[str, object]]:
    tasks = db.scalars(select(ResearchTask).where(ResearchTask.niche_id == niche_id)).all()
    payload = []
    for task in tasks:
        for trajectory in task.trajectories:
            payload.append(
                {
                    "task_id": task.id,
                    "prompt": task.prompt,
                    "evaluation_type": task.evaluation_type,
                    "reward_definition": task.reward_definition,
                    "trajectory_id": trajectory.id,
                    "policy_name": trajectory.policy_name,
                    "final_answer": trajectory.final_answer,
                    "total_reward": trajectory.total_reward,
                    "steps": [
                        {
                            "node_key": step.node_key,
                            "action_type": step.action_type,
                            "action_input": step.action_input,
                            "observation": step.observation,
                            "branch_score": step.branch_score,
                        }
                        for step in trajectory.steps
                    ],
                    "rewards": [
                        {
                            "reward_name": reward.reward_name,
                            "reward_value": reward.reward_value,
                            "reason": reward.reason,
                        }
                        for reward in trajectory.rewards
                    ],
                }
            )
    return payload


def _collect_snapshot_evidence(
    db: Session, niche_id: int, company_id: int | None
) -> list[dict[str, object]]:
    query = (
        select(PageSnapshot, SourcePage, Company)
        .join(SourcePage, PageSnapshot.source_id == SourcePage.id)
        .join(Company, SourcePage.company_id == Company.id)
        .where(Company.niche_id == niche_id)
        .order_by(PageSnapshot.fetched_at.desc())
    )
    if company_id is not None:
        query = query.where(Company.id == company_id)

    rows = db.execute(query).all()
    grouped = defaultdict(list)
    for snapshot, source, company in rows:
        grouped[source.id].append((snapshot, source, company))

    evidence = []
    for source_rows in grouped.values():
        snapshot, source, company = source_rows[0]
        score = _page_type_score(source.page_type)
        summary = snapshot.summary_text or snapshot.title or ""
        evidence.append(
            {
                "snapshot_id": snapshot.id,
                "scrape_run_id": snapshot.scrape_run_id,
                "company": company.name,
                "page_type": source.page_type,
                "url": source.url,
                "summary": summary[:400],
                "score": score,
                "signals": _extract_signal_tokens(summary),
            }
        )
    evidence.sort(key=lambda item: float(item["score"]), reverse=True)
    return evidence[:16]


def _compose_answer(prompt: str, evidence: list[dict[str, object]]) -> str:
    if not evidence:
        return f"No saved evidence is available yet for: {prompt}"

    themes = _group_signals(evidence)
    strongest_sources = ", ".join(item["company"] for item in evidence[:3])
    highlights = []
    for item in evidence[:3]:
        highlights.append(
            f"- {item['company']} | {item['page_type']} | score {item['score']}: {item['summary']}"
        )

    theme_lines = []
    for theme, count in themes[:3]:
        theme_lines.append(f"- {theme}: observed across {count} source(s)")

    next_watch = _build_watchlist(evidence)
    return (
        f"Question: {prompt}\n"
        "Approach: a quick pass across the most recent saved pages.\n"
        f"Strongest sources: {strongest_sources}\n"
        "What stood out:\n"
        f"{chr(10).join(highlights)}\n"
        "Emerging themes:\n"
        f"{chr(10).join(theme_lines) if theme_lines else '- No repeated themes yet'}\n"
        f"Next to check: {next_watch}"
    )


def _score_trajectory(evidence: list[dict[str, object]]) -> dict[str, float | int]:
    evidence_count = len(evidence)
    source_coverage = min(1.0, evidence_count / 3)
    diversity = min(1.0, len({item['page_type'] for item in evidence}) / 3) if evidence else 0.0
    freshness = 1.0 if evidence_count > 0 else 0.0
    return {
        "evidence_count": evidence_count,
        "source_coverage": source_coverage,
        "freshness": freshness,
        "diversity": diversity,
        "total": round(source_coverage * 0.5 + freshness * 0.2 + diversity * 0.3, 3),
    }


@dataclass(frozen=True)
class SearchStepDraft:
    node_key: str
    parent_key: str | None
    snapshot_id: int | None
    step_index: int
    action_type: str
    action_input: str
    observation: str | None
    branch_score: float | None


def _build_tree_search(
    prompt: str,
    evidence: list[dict[str, object]],
    *,
    max_depth: int = 3,
    branch_factor: int = 2,
    rollout_limit: int = 4,
) -> dict[str, object]:
    steps: list[SearchStepDraft] = [
        SearchStepDraft(
            node_key="root",
            parent_key=None,
            snapshot_id=None,
            step_index=0,
            action_type="plan_search",
            action_input=prompt,
            observation=f"Initialized tree search across {len(evidence)} evidence nodes.",
            branch_score=1.0 if evidence else 0.0,
        )
    ]
    if not evidence:
        return {
            "steps": steps,
            "rollouts": [],
            "selected_evidence": [],
            "achieved_depth": 0,
        }

    seeds = _select_seed_evidence(evidence, rollout_limit)
    expansions: dict[str, list[str]] = defaultdict(list)
    evidence_by_key: dict[str, dict[str, object]] = {}
    queue: list[tuple[str, dict[str, object], int, set[int]]] = []
    step_index = 1

    for seed_index, item in enumerate(seeds, start=1):
        node_key = f"root.branch_{seed_index}"
        steps.append(
            SearchStepDraft(
                node_key=node_key,
                parent_key="root",
                snapshot_id=int(item["snapshot_id"]),
                step_index=step_index,
                action_type="inspect_snapshot",
                action_input=str(item["url"]),
                observation=str(item["summary"]),
                branch_score=float(item["score"]),
            )
        )
        expansions["root"].append(node_key)
        evidence_by_key[node_key] = item
        queue.append((node_key, item, 1, {int(item["snapshot_id"])}))
        step_index += 1

    while queue:
        parent_key, parent_item, depth, used_snapshot_ids = queue.pop(0)
        if depth >= max_depth:
            continue

        children = _select_child_evidence(
            parent_item,
            evidence,
            used_snapshot_ids,
            branch_factor,
        )
        for child_index, child in enumerate(children, start=1):
            child_key = f"{parent_key}.branch_{child_index}"
            branch_score = _score_child_branch(parent_item, child)
            steps.append(
                SearchStepDraft(
                    node_key=child_key,
                    parent_key=parent_key,
                    snapshot_id=int(child["snapshot_id"]),
                    step_index=step_index,
                    action_type="expand_branch",
                    action_input=str(child["url"]),
                    observation=str(child["summary"]),
                    branch_score=branch_score,
                )
            )
            expansions[parent_key].append(child_key)
            evidence_by_key[child_key] = child
            queue.append(
                (
                    child_key,
                    child,
                    depth + 1,
                    used_snapshot_ids | {int(child["snapshot_id"])},
                )
            )
            step_index += 1

    rollouts = _extract_rollouts(expansions, evidence_by_key, rollout_limit)
    selected_evidence = _unique_evidence_from_rollouts(rollouts)
    achieved_depth = max((rollout["depth"] for rollout in rollouts), default=0)
    return {
        "steps": steps,
        "rollouts": rollouts,
        "selected_evidence": selected_evidence,
        "achieved_depth": achieved_depth,
    }


def _persist_tree_steps(
    db: Session, trajectory_id: int, step_drafts: list[SearchStepDraft]
) -> dict[str, int]:
    step_id_by_key: dict[str, int] = {}
    for draft in sorted(step_drafts, key=lambda item: item.step_index):
        step = TrajectoryStep(
            trajectory_id=trajectory_id,
            parent_step_id=step_id_by_key.get(draft.parent_key) if draft.parent_key else None,
            snapshot_id=draft.snapshot_id,
            node_key=draft.node_key,
            step_index=draft.step_index,
            action_type=draft.action_type,
            action_input=draft.action_input,
            observation=draft.observation,
            branch_score=draft.branch_score,
        )
        db.add(step)
        db.flush()
        step_id_by_key[draft.node_key] = step.id
    return step_id_by_key


def _record_tree_rewards(
    db: Session,
    trajectory_id: int,
    reward: dict[str, float | int],
    rollouts: list[dict[str, object]],
    step_id_by_key: dict[str, int],
) -> None:
    reward_specs = (
        ("source_coverage", reward["source_coverage"], f"{reward['evidence_count']} evidence pages explored"),
        ("source_diversity", reward["diversity"], "Different page types improved branch coverage"),
        ("freshness", reward["freshness"], "Recent snapshots receive higher reward"),
        ("tree_depth", reward["tree_depth"], "Deeper valid branches improve search quality"),
        ("rollout_exploration", reward["exploration"], "Multiple candidate rollout paths were sampled"),
        ("signal_density", reward["signal_density"], "Denser page signals improve summary quality"),
    )
    for reward_name, reward_value, reason in reward_specs:
        db.add(
            RewardRecord(
                trajectory_id=trajectory_id,
                reward_name=reward_name,
                reward_value=float(reward_value),
                reason=reason,
            )
        )

    for rollout_index, rollout in enumerate(rollouts, start=1):
        leaf_key = str(rollout["path"][-1]) if rollout["path"] else None
        db.add(
            RewardRecord(
                trajectory_id=trajectory_id,
                step_id=step_id_by_key.get(leaf_key) if leaf_key else None,
                reward_name=f"rollout_{rollout_index}",
                reward_value=float(rollout["score"]),
                reason=f"Path: {' -> '.join(str(node) for node in rollout['path'])}",
            )
        )


def _compose_tree_answer(
    prompt: str, rollouts: list[dict[str, object]], evidence: list[dict[str, object]]
) -> str:
    if not evidence:
        return f"No saved evidence is available yet for: {prompt}"

    if not rollouts:
        return _compose_answer(prompt, evidence[:4])

    strongest_sources = []
    for rollout in rollouts[:3]:
        if rollout["evidence"]:
            strongest_sources.append(str(rollout["evidence"][0]["company"]))

    observations = []
    for rollout_index, rollout in enumerate(rollouts[:3], start=1):
        companies = ", ".join(str(item["company"]) for item in rollout["evidence"])
        pages = ", ".join(str(item["page_type"]) for item in rollout["evidence"])
        observations.append(
            f"- rollout {rollout_index} | score {rollout['score']}: companies [{companies}] across [{pages}]"
        )

    themes = _group_signals(_unique_evidence_from_rollouts(rollouts))
    theme_lines = [f"- {theme}: observed across {count} branch(es)" for theme, count in themes[:4]]
    watchlist = _build_watchlist(_unique_evidence_from_rollouts(rollouts))
    return (
        f"Question: {prompt}\n"
        "Approach: a deeper pass over the strongest saved pages.\n"
        f"Top sources: {', '.join(strongest_sources) if strongest_sources else 'n/a'}\n"
        "Best source paths:\n"
        f"{chr(10).join(observations)}\n"
        "Shared themes:\n"
        f"{chr(10).join(theme_lines) if theme_lines else '- No repeated themes yet'}\n"
        f"Next to check: {watchlist}"
    )


def _score_tree_trajectory(
    evidence: list[dict[str, object]],
    rollouts: list[dict[str, object]],
    *,
    achieved_depth: int,
    target_depth: int = 3,
) -> dict[str, float | int]:
    base = _score_trajectory(evidence)
    exploration = min(1.0, len(rollouts) / 4) if rollouts else 0.0
    tree_depth = min(1.0, achieved_depth / target_depth) if achieved_depth else 0.0
    signal_density = 0.0
    if evidence:
        signal_density = min(
            1.0,
            sum(len(item.get("signals") or []) for item in evidence) / max(len(evidence) * 2, 1),
        )
    total = round(
        float(base["source_coverage"]) * 0.3
        + float(base["diversity"]) * 0.2
        + float(base["freshness"]) * 0.15
        + exploration * 0.15
        + tree_depth * 0.1
        + signal_density * 0.1,
        3,
    )
    return {
        **base,
        "exploration": exploration,
        "tree_depth": tree_depth,
        "signal_density": signal_density,
        "total": total,
    }


def _select_seed_evidence(
    evidence: list[dict[str, object]], limit: int
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    seen_companies: set[str] = set()
    for item in evidence:
        company = str(item["company"])
        if company in seen_companies and len(selected) < max(2, limit // 2):
            continue
        selected.append(item)
        seen_companies.add(company)
        if len(selected) >= limit:
            break
    return selected


def _select_child_evidence(
    parent: dict[str, object],
    evidence: list[dict[str, object]],
    used_snapshot_ids: set[int],
    branch_factor: int,
) -> list[dict[str, object]]:
    candidates: list[tuple[float, dict[str, object]]] = []
    for candidate in evidence:
        snapshot_id = int(candidate["snapshot_id"])
        if snapshot_id in used_snapshot_ids:
            continue
        score = _score_child_branch(parent, candidate)
        if score < 0.55:
            continue
        candidates.append((score, candidate))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in candidates[:branch_factor]]


def _score_child_branch(parent: dict[str, object], candidate: dict[str, object]) -> float:
    same_company = 0.12 if parent["company"] == candidate["company"] else 0.0
    signal_overlap = len(set(parent.get("signals") or []).intersection(candidate.get("signals") or []))
    page_type_bonus = 0.08 if parent["page_type"] != candidate["page_type"] else 0.0
    return round(
        min(
            1.0,
            float(candidate["score"]) * 0.72
            + (0.08 * signal_overlap)
            + same_company
            + page_type_bonus,
        ),
        3,
    )


def _extract_rollouts(
    expansions: dict[str, list[str]],
    evidence_by_key: dict[str, dict[str, object]],
    rollout_limit: int,
) -> list[dict[str, object]]:
    rollouts: list[dict[str, object]] = []

    def walk(node_key: str, path: list[str]) -> None:
        children = expansions.get(node_key, [])
        next_path = path + [node_key]
        if not children:
            evidence = [evidence_by_key[key] for key in next_path if key in evidence_by_key]
            score = round(sum(float(item["score"]) for item in evidence) / max(len(evidence), 1), 3)
            rollouts.append(
                {
                    "path": next_path,
                    "evidence": evidence,
                    "score": score,
                    "depth": len(next_path),
                }
            )
            return
        for child_key in children:
            walk(child_key, next_path)

    for root_child in expansions.get("root", []):
        walk(root_child, [])

    rollouts.sort(key=lambda item: (float(item["score"]), int(item["depth"])), reverse=True)
    return rollouts[:rollout_limit]


def _unique_evidence_from_rollouts(rollouts: list[dict[str, object]]) -> list[dict[str, object]]:
    unique: dict[int, dict[str, object]] = {}
    for rollout in rollouts:
        for item in rollout["evidence"]:
            unique[int(item["snapshot_id"])] = item
    return list(unique.values())


def _page_type_score(page_type: str) -> float:
    scores = {
        "pricing": 1.0,
        "homepage": 0.96,
        "product": 0.93,
        "careers": 0.88,
        "docs": 0.84,
        "industry-news": 0.82,
        "analysis": 0.8,
        "market-data": 0.78,
        "community-signal": 0.76,
        "macro-news": 0.7,
    }
    return scores.get(page_type, 0.72)


def _extract_signal_tokens(text: str) -> list[str]:
    lowered = text.lower()
    candidates = (
        "pricing",
        "launch",
        "hiring",
        "funding",
        "policy",
        "ai",
        "energy",
        "acquisition",
        "product",
        "market",
        "enterprise",
        "security",
    )
    return [token for token in candidates if token in lowered]


def _group_signals(evidence: Iterable[dict[str, object]]) -> list[tuple[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    for item in evidence:
        signals = item.get("signals") or []
        if not signals:
            counts[str(item["page_type"])] += 1
            continue
        for signal in signals:
            counts[str(signal)] += 1
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def _build_watchlist(evidence: list[dict[str, object]]) -> str:
    if not evidence:
        return "Wait for the first completed scrape."

    page_types = sorted({str(item["page_type"]) for item in evidence})
    companies = ", ".join(item["company"] for item in evidence[:3])
    return f"Monitor {', '.join(page_types)} pages and revisit leading sources from {companies}."
