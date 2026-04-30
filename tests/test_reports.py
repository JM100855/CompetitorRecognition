from app.services.agent import (
    _build_tree_search,
    _compose_answer,
    _score_trajectory,
    _score_tree_trajectory,
)


def test_score_trajectory_rewards_available_evidence() -> None:
    reward = _score_trajectory(
        [
            {"company": "A", "page_type": "homepage", "summary": "Fresh", "score": 1.0},
            {"company": "B", "page_type": "pricing", "summary": "Pricing update", "score": 1.0},
        ]
    )

    assert reward["source_coverage"] > 0
    assert reward["diversity"] > 0
    assert reward["total"] > 0


def test_compose_answer_mentions_prompt_and_company() -> None:
    answer = _compose_answer(
        "Which competitor is moving upmarket?",
        [
            {
                "company": "ExampleCo",
                "page_type": "pricing",
                "summary": "Enterprise plan and SSO were added.",
                "score": 1.0,
                "signals": ["pricing", "enterprise"],
            }
        ],
    )

    assert "Which competitor is moving upmarket?" in answer
    assert "ExampleCo" in answer
    assert "Emerging themes" in answer


def test_build_tree_search_creates_nested_rollouts() -> None:
    result = _build_tree_search(
        "Which competitor is expanding fastest?",
        [
            {
                "snapshot_id": 1,
                "scrape_run_id": 1,
                "company": "ExampleCo",
                "page_type": "homepage",
                "url": "https://example.com/",
                "summary": "AI launch and enterprise push.",
                "score": 0.95,
                "signals": ["ai", "enterprise", "launch"],
            },
            {
                "snapshot_id": 2,
                "scrape_run_id": 1,
                "company": "ExampleCo",
                "page_type": "pricing",
                "url": "https://example.com/pricing",
                "summary": "New enterprise pricing tiers.",
                "score": 0.98,
                "signals": ["pricing", "enterprise"],
            },
            {
                "snapshot_id": 3,
                "scrape_run_id": 1,
                "company": "RivalCo",
                "page_type": "careers",
                "url": "https://rival.com/careers",
                "summary": "Hiring across sales and AI engineering.",
                "score": 0.88,
                "signals": ["hiring", "ai"],
            },
        ],
        max_depth=2,
        branch_factor=2,
        rollout_limit=3,
    )

    assert result["rollouts"]
    assert result["achieved_depth"] >= 1
    assert any(step.node_key.startswith("root.branch_") for step in result["steps"])
    assert any(".branch_" in rollout["path"][-1] for rollout in result["rollouts"])


def test_score_tree_trajectory_rewards_exploration() -> None:
    reward = _score_tree_trajectory(
        [
            {"page_type": "homepage", "signals": ["ai", "launch"], "score": 0.9},
            {"page_type": "pricing", "signals": ["pricing"], "score": 1.0},
        ],
        [
            {
                "path": ["root.branch_1", "root.branch_1.branch_1"],
                "evidence": [{"score": 0.9}, {"score": 1.0}],
                "score": 0.95,
                "depth": 2,
            }
        ],
        achieved_depth=2,
    )

    assert reward["exploration"] > 0
    assert reward["tree_depth"] > 0
    assert reward["signal_density"] > 0
    assert reward["total"] > 0
