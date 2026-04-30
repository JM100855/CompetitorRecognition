from app.services import discovery
from app.services.discovery import DiscoveredSource, discover_sources_for_niche


def test_discover_sources_for_tech_returns_technology_sources() -> None:
    results = discover_sources_for_niche("tech")

    assert results
    companies = {item.company_name for item in results}
    assert "TechCrunch" in companies
    assert "Hacker News" in companies


def test_discover_sources_for_oil_and_gas_returns_energy_sources() -> None:
    results = discover_sources_for_niche("oil and gas")

    assert results
    companies = {item.company_name for item in results}
    assert "Reuters Energy" in companies
    assert "U.S. Energy Information Administration" in companies


def test_hybrid_discovery_merges_llm_sources(monkeypatch) -> None:
    monkeypatch.setattr(discovery.settings, "discovery_strategy", "hybrid")
    monkeypatch.setattr(discovery.settings, "max_discovered_sources", 12)

    def fake_llm(name: str, description: str | None = None) -> list[DiscoveredSource]:
        return [
            DiscoveredSource(
                company_name="Acme Robotics",
                domain="acmerobotics.example",
                page_type="vendor-site",
                url="https://acmerobotics.example/",
                rationale="Synthetic competitor from LLM discovery.",
                score=0.99,
            )
        ]

    monkeypatch.setattr("app.services.llm_discovery.discover_sources_with_ollama", fake_llm)
    results = discover_sources_for_niche("robotics")

    companies = {item.company_name for item in results}
    page_types = {item.page_type for item in results if item.company_name == "Acme Robotics"}
    assert "Acme Robotics" in companies
    assert "Reuters Business" in companies
    assert "pricing" in page_types
    assert "careers" in page_types


def test_vendor_homepage_expands_into_multiple_scrape_targets(monkeypatch) -> None:
    monkeypatch.setattr(discovery.settings, "discovery_strategy", "ollama")
    monkeypatch.setattr(discovery.settings, "max_discovered_sources", 10)

    def fake_llm(name: str, description: str | None = None) -> list[DiscoveredSource]:
        return [
            DiscoveredSource(
                company_name="Northstar AI",
                domain="northstar.ai",
                page_type="homepage",
                url="https://northstar.ai/",
                rationale="Direct competitor homepage.",
                score=0.97,
            )
        ]

    monkeypatch.setattr("app.services.llm_discovery.discover_sources_with_ollama", fake_llm)
    results = discover_sources_for_niche("ai coding")

    urls = {item.url for item in results}
    assert "https://northstar.ai/" in urls
    assert "https://northstar.ai/pricing" in urls
    assert "https://northstar.ai/product" in urls
    assert "https://northstar.ai/careers" in urls
