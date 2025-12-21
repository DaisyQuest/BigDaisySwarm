from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class ParameterSpec:
    """Specification for a numeric agent parameter."""

    name: str
    param_type: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_value: Optional[float] = None
    description: str = ""

    def validate_value(self, value: float) -> None:
        """Validate a provided value against the parameter spec."""
        if value is None:
            raise ValueError(f"Parameter '{self.name}' requires a numeric value")

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Parameter '{self.name}' must be numeric")

        if self.min_value is not None and value < self.min_value:
            raise ValueError(
                f"Parameter '{self.name}' must be >= {self.min_value}; received {value}"
            )

        if self.max_value is not None and value > self.max_value:
            raise ValueError(
                f"Parameter '{self.name}' must be <= {self.max_value}; received {value}"
            )


@dataclass(frozen=True)
class AgentType:
    """Represents an agent type and its tunable parameters."""

    name: str
    description: str
    parameters: List[ParameterSpec] = field(default_factory=list)

    @property
    def parameter_index(self) -> Dict[str, ParameterSpec]:
        return {param.name: param for param in self.parameters}

    def to_dict(self) -> Dict[str, object]:
        return {
            "description": self.description,
            "parameters": {
                parameter.name: {
                    "type": parameter.param_type,
                    "min": parameter.min_value,
                    "max": parameter.max_value,
                    "default": parameter.default_value,
                    "description": parameter.description,
                }
                for parameter in self.parameters
            },
        }

    def validate_config(self, config: Mapping[str, object]) -> None:
        unknown_parameters = set(config.keys()) - set(self.parameter_index.keys())
        if unknown_parameters:
            unknown = ", ".join(sorted(unknown_parameters))
            raise ValueError(
                f"Agent '{self.name}' received unknown parameters: {unknown}"
            )

        for parameter in self.parameters:
            if parameter.name not in config:
                raise ValueError(
                    f"Agent '{self.name}' is missing parameter '{parameter.name}'"
                )
            parameter.validate_value(config[parameter.name])


@dataclass(frozen=True)
class AgentInstance:
    """Concrete agent instance used in a project team."""

    id: str
    type_name: str
    parameters: Mapping[str, object]


REQUIRED_AGENT_NAMES = (
    "Architect",
    "Developer",
    "TestEngineer",
    "Critic",
    "NoteTaker",
    "Arbiter",
)

DEFAULT_AGENT_DEFINITIONS_PATH = Path(__file__).resolve().parents[2] / "agents" / "AGENTS.json"


def load_agent_types_from_json(definitions: Mapping[str, Any]) -> List[AgentType]:
    if not isinstance(definitions, Mapping):
        raise ValueError("Agent definitions must be a mapping of agent name to definition")

    agent_types: List[AgentType] = []
    for agent_name, raw_definition in definitions.items():
        if not isinstance(raw_definition, Mapping):
            raise ValueError(f"Agent definition for '{agent_name}' must be a mapping")

        parameters_data = raw_definition.get("parameters")
        if not isinstance(parameters_data, Mapping):
            raise ValueError(f"Agent definition for '{agent_name}' must include a 'parameters' mapping")

        parameters: List[ParameterSpec] = []
        for parameter_name, parameter_definition in parameters_data.items():
            if not isinstance(parameter_definition, Mapping):
                raise ValueError(
                    f"Parameter '{parameter_name}' for agent '{agent_name}' must be a mapping"
                )

            param_type = parameter_definition.get("type")
            if not isinstance(param_type, str) or not param_type:
                raise ValueError(
                    f"Parameter '{parameter_name}' for agent '{agent_name}' must declare a string 'type'"
                )

            spec = ParameterSpec(
                name=parameter_name,
                param_type=param_type,
                min_value=parameter_definition.get("min"),
                max_value=parameter_definition.get("max"),
                default_value=parameter_definition.get("default"),
                description=parameter_definition.get("description", ""),
            )
            if spec.default_value is not None:
                spec.validate_value(spec.default_value)
            parameters.append(spec)

        agent_types.append(
            AgentType(
                name=agent_name,
                description=str(raw_definition.get("description", "")),
                parameters=parameters,
            )
        )

    missing = set(REQUIRED_AGENT_NAMES) - {agent_type.name for agent_type in agent_types}
    if missing:
        raise ValueError("Agent definitions missing required types: " + ", ".join(sorted(missing)))

    return agent_types


def load_agent_types_from_file(definitions_path: Path) -> List[AgentType]:
    if not definitions_path.is_file():
        raise ValueError(f"Agent definitions not found at {definitions_path}")

    try:
        with definitions_path.open(encoding="utf-8") as definitions_file:
            definitions = json.load(definitions_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse agent definitions at {definitions_path}: {exc}") from exc

    return load_agent_types_from_json(definitions)


def _bounded_double(name: str, description: str) -> ParameterSpec:
    return ParameterSpec(
        name=name,
        param_type="double",
        min_value=0.0,
        max_value=1.0,
        default_value=0.5,
        description=description,
    )


def default_agent_types() -> List[AgentType]:
    """Return the canonical set of agent types defined in the spec."""

    prefer_simplicity = _bounded_double(
        "preferSimplicityLevel",
        "Higher values prioritize simple, maintainable solutions.",
    )
    prefer_homebaked = _bounded_double(
        "preferHomebakedCodeLevel",
        "Higher values favor bespoke implementations over third-party libraries.",
    )

    return [
        AgentType(
            name="Architect",
            description="Maintains the project spec and validates work against it.",
            parameters=[prefer_simplicity, prefer_homebaked],
        ),
        AgentType(
            name="Developer",
            description="Implements features to meet the specification and commits code.",
            parameters=[prefer_simplicity, prefer_homebaked],
        ),
        AgentType(
            name="TestEngineer",
            description=(
                "Develops tests aiming for comprehensive coverage and recommends "
                "testability improvements."
            ),
        ),
        AgentType(
            name="Critic",
            description="Identifies risks, maintainability concerns, and potential flaws.",
        ),
        AgentType(
            name="NoteTaker",
            description="Summarizes meetings and prepares reports for the Arbiter.",
        ),
        AgentType(
            name="Arbiter",
            description="Reviews opinions and calls for next actions or resolutions.",
        ),
    ]


def agent_type_index(agent_types: Iterable[AgentType]) -> Dict[str, AgentType]:
    return {agent_type.name: agent_type for agent_type in agent_types}


def _default_parameters(agent_type: AgentType) -> Dict[str, float]:
    parameters: Dict[str, float] = {}
    for parameter in agent_type.parameters:
        if parameter.default_value is None:
            raise ValueError(
                f"No default value provided for parameter '{parameter.name}' in agent '{agent_type.name}'"
            )
        parameters[parameter.name] = parameter.default_value
    return parameters


def default_team_config(
    agent_types: Optional[Iterable[AgentType]] = None,
) -> List[Dict[str, object]]:
    """Generate a default team configuration with two architects."""
    agent_types = list(agent_types) if agent_types is not None else default_agent_types()
    index = agent_type_index(agent_types)

    def params_for(agent_name: str, overrides: Optional[Mapping[str, float]] = None) -> Dict[str, float]:
        base = _default_parameters(index[agent_name])
        if overrides:
            base.update(overrides)
        return base

    instances = [
        AgentInstance(
            id="ArchitectA",
            type_name="Architect",
            parameters=params_for("Architect", overrides={"preferSimplicityLevel": 0.6, "preferHomebakedCodeLevel": 0.4}),
        ),
        AgentInstance(
            id="ArchitectB",
            type_name="Architect",
            parameters=params_for("Architect", overrides={"preferSimplicityLevel": 0.3, "preferHomebakedCodeLevel": 0.7}),
        ),
        AgentInstance(
            id="Developer",
            type_name="Developer",
            parameters=params_for("Developer"),
        ),
        AgentInstance(id="TestEngineer", type_name="TestEngineer", parameters={}),
        AgentInstance(id="Critic", type_name="Critic", parameters={}),
        AgentInstance(id="NoteTaker", type_name="NoteTaker", parameters={}),
        AgentInstance(id="Arbiter", type_name="Arbiter", parameters={}),
    ]

    known_types = {instance.type_name for instance in instances}
    for agent_type in agent_types:
        if agent_type.name in known_types:
            continue
        instances.append(
            AgentInstance(
                id=agent_type.name,
                type_name=agent_type.name,
                parameters=_default_parameters(agent_type),
            )
        )

    return [
        {"id": instance.id, "type": instance.type_name, "parameters": dict(instance.parameters)}
        for instance in instances
    ]


def validate_team_config(
    team_config: Sequence[Mapping[str, object]],
    agent_types: Optional[Iterable[AgentType]] = None,
) -> None:
    """Validate a parsed team configuration against the canonical agent types."""
    if not isinstance(team_config, (list, tuple)):
        raise ValueError("Team configuration must be a list of agent instance mappings")

    agent_types = list(agent_types) if agent_types is not None else default_agent_types()
    index = agent_type_index(agent_types)

    seen_ids = set()
    seen_types = set()

    for entry in team_config:
        if not isinstance(entry, Mapping):
            raise ValueError("Each team configuration entry must be a mapping")

        missing_fields = [field for field in ("id", "type", "parameters") if field not in entry]
        if missing_fields:
            raise ValueError(
                "Missing required fields in agent entry: " + ", ".join(sorted(missing_fields))
            )

        agent_id = entry["id"]
        agent_type_name = entry["type"]
        parameters = entry["parameters"]

        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError("Agent id must be a non-empty string")

        if agent_id in seen_ids:
            raise ValueError(f"Duplicate agent id detected: {agent_id}")
        seen_ids.add(agent_id)

        if agent_type_name not in index:
            raise ValueError("Unknown agent types: " + agent_type_name)
        seen_types.add(agent_type_name)

        if not isinstance(parameters, Mapping):
            raise ValueError(f"Agent '{agent_id}' parameters must be a mapping")

        index[agent_type_name].validate_config(parameters)

    missing = set(REQUIRED_AGENT_NAMES) - seen_types
    if missing:
        raise ValueError("Missing required agent types: " + ", ".join(sorted(missing)))
