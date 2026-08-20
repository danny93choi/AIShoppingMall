from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from string import Formatter
from typing import Any


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    version: str
    system_template: str
    user_template: str
    content_hash: str

    def render(self, values: dict[str, Any]) -> tuple[str, str]:
        required = {
            field_name
            for template in (self.system_template, self.user_template)
            for _, field_name, _, _ in Formatter().parse(template)
            if field_name
        }
        missing = required - values.keys()
        if missing:
            raise ValueError(f"missing prompt values: {', '.join(sorted(missing))}")
        return self.system_template.format_map(values), self.user_template.format_map(values)


class PromptRegistry:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def load(self, name: str, version: str) -> PromptTemplate:
        path = (self._root / name / f"{version}.md").resolve()
        if self._root not in path.parents:
            raise ValueError("prompt path escapes registry root")
        content = path.read_text(encoding="utf-8")
        marker = "\n## User\n"
        if not content.startswith("## System\n") or marker not in content:
            raise ValueError("prompt must contain '## System' and '## User' sections")
        system, user = content.removeprefix("## System\n").split(marker, maxsplit=1)
        return PromptTemplate(
            name=name,
            version=version,
            system_template=system.strip(),
            user_template=user.strip(),
            content_hash=sha256(content.encode()).hexdigest(),
        )
