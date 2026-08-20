from httpx import AsyncClient


async def test_admin_shell_contains_required_operator_surfaces(client: AsyncClient) -> None:
    response = await client.get("/admin")
    assert response.status_code == 200
    html = response.text
    for label in (
        "AI Commerce Control Room",
        "새 Discovery 실행",
        "Top Recommendations",
        "Candidates",
        "Marketing Drafts",
        "Agent Runs",
        "Integrations",
    ):
        assert label in html
