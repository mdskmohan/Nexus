"""What a connection needs, declared once per warehouse.

The web app renders the connection form from these fields and the API
validates against them. Secret fields are stored encrypted, apart from the
rest, and are never returned by the API, written to a log or put in an error.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Field:
    name: str
    label: str
    required: bool = True
    secret: bool = False
    multiline: bool = False
    help: str = ""
    placeholder: str = ""
    default: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Spec:
    kind: str
    name: str
    description: str
    fields: tuple[Field, ...]
    docs_url: str = ""
    # False until the connector has been exercised against a real account.
    verified: bool = False

    def split(self, values: dict) -> tuple[dict, dict]:
        """(settings, secrets) from submitted values, dropping blanks and unknown names."""
        settings, secrets = {}, {}
        for f in self.fields:
            value = values.get(f.name)
            if isinstance(value, str):
                value = value.strip() if not f.multiline else value.strip("\n")
            if value in (None, ""):
                continue
            (secrets if f.secret else settings)[f.name] = str(value)
        return settings, secrets

    def problems(self, settings: dict, secrets: dict) -> list[str]:
        """Plain problems with a configuration, empty if it is complete."""
        out = []
        for f in self.fields:
            value = (secrets if f.secret else settings).get(f.name)
            if f.required and not value:
                out.append(f"{f.label} is required.")
            elif value and f.options and value not in f.options:
                out.append(f"{f.label} must be one of: {', '.join(f.options)}.")
        return out

    def public(self) -> dict:
        return {"kind": self.kind, "name": self.name, "description": self.description, "docs_url": self.docs_url,
                "verified": self.verified,
                "fields": [{"name": f.name, "label": f.label, "required": f.required, "secret": f.secret,
                            "multiline": f.multiline, "help": f.help, "placeholder": f.placeholder,
                            "default": f.default, "options": list(f.options)} for f in self.fields]}


@dataclass(frozen=True, slots=True)
class TestResult:
    ok: bool
    message: str
    details: dict[str, str] = field(default_factory=dict)
