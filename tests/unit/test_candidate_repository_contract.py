import inspect

from commerce_agent.domain.repositories import ProductCandidateRepository


def test_candidate_repository_requires_tenant_id() -> None:
    for method_name in ("add", "get_by_id", "list"):
        signature = inspect.signature(getattr(ProductCandidateRepository, method_name))
        assert "tenant_id" in signature.parameters
