from httpx import AsyncClient


async def test_admin_shell_contains_required_operator_surfaces(client: AsyncClient) -> None:
    response = await client.get("/admin")
    assert response.status_code == 200
    html = response.text
    for label in (
        "AI Commerce Control Room",
        "시장조사 추천",
        "조사 데이터 상세",
        "판매 준비",
        "AI Agent 실행",
        "데이터 연결",
        "자동 상품 발굴",
        "쇼핑 대분류",
        "세부 상품군",
        "refreshSubcategories",
        "수납정리용품",
        "최소 월간 검색량",
        "20개 상품 후보 발굴",
        "네이버 쇼핑 트렌드 추이",
        "lineChart",
        "실제 조사 상품",
        "최근 3개월",
        "계절성 강도",
        "예상 성수기",
        "자동 발굴 품질 검토",
        "트렌드 데이터 미제공",
        "판매조건 입력",
        "예상 판매가",
        "손익분기",
        "현재 AI Agent는 동작하지 않습니다.",
        "errorMessage",
        "연결 정보 초기화",
        "restoreConnection",
        "localStorage.removeItem",
    ):
        assert label in html
    assert "데모 데이터" not in html
