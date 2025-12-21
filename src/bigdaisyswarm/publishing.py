from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from .agents import validate_team_config


@dataclass(frozen=True)
class PublishingChannel:
    """Publishing target for the universal pipeline."""

    name: str
    medium: str
    requires_client_sync: bool = False
    requires_backend_sync: bool = False
    notes: str = ""

    def validate(self) -> None:
        if not self.name:
            raise ValueError("channel name is required")
        if not self.medium:
            raise ValueError("channel medium is required")


@dataclass(frozen=True)
class PublishingStage:
    """Single step in a publishing plan."""

    name: str
    owner: str
    description: str
    channels: Tuple[str, ...]
    checklist: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "owner": self.owner,
            "description": self.description,
            "channels": list(self.channels),
            "checklist": list(self.checklist),
        }


class PublishingPipeline:
    """Coordinate an additive publishing pipeline across channels."""

    def __init__(
        self,
        *,
        task: str,
        team_config: Sequence[Mapping[str, object]],
        channels: Sequence[PublishingChannel],
        release_mode: str = "additive",
    ) -> None:
        if not task:
            raise ValueError("task is required to build a publishing pipeline")
        if not channels:
            raise ValueError("at least one publishing channel is required")
        if release_mode not in {"additive", "breaking"}:
            raise ValueError("release_mode must be 'additive' or 'breaking'")

        self.task = task
        self.release_mode = release_mode
        self._channels = list(channels)
        self._validate_channels()

        validate_team_config(team_config)
        self._agent_index = self._index_agents(team_config)

    def build_plan(self) -> List[PublishingStage]:
        channel_names = tuple(channel.name for channel in self._channels)

        stages = [
            PublishingStage(
                name="Specification alignment",
                owner=self._owner_for("Architect"),
                description=f"Translate '{self.task}' into guardrails for every publishing surface.",
                channels=channel_names,
                checklist=(
                    "Document the definition of done and rollout metrics for the pipeline.",
                    self._compatibility_checkpoint(),
                ),
            ),
            PublishingStage(
                name="Implementation and packaging",
                owner=self._owner_for("Developer"),
                description="Build adapters and automation that keep releases additive.",
                channels=channel_names,
                checklist=(
                    "Prefer additive rollout steps to avoid blocking client and backend teams.",
                    "Provide reusable adapters for each publishing medium.",
                ),
            ),
            PublishingStage(
                name="Quality assurance",
                owner=self._owner_for("TestEngineer"),
                description="Exercise happy and sad paths for all channels.",
                channels=channel_names,
                checklist=(
                    "Validate payload shape, metadata handling, and failure retries per channel.",
                    "Assert telemetry is emitted for both success and failure paths.",
                ),
            ),
            PublishingStage(
                name="Risk review",
                owner=self._owner_for("Critic"),
                description="Surface rollout risks and mitigation strategies.",
                channels=channel_names,
                checklist=(
                    "Call out cross-team conflicts and propose mitigation or sequencing.",
                    "List rollback and isolation options for each publishing surface.",
                ),
            ),
            PublishingStage(
                name="Go / No-go",
                owner=self._owner_for("Arbiter"),
                description="Approve release after each gate owner signs off.",
                channels=channel_names,
                checklist=(
                    "Confirm Architect, Developer, TestEngineer, and Critic checkpoints are complete.",
                    "Ratify additive rollout posture before enabling channels.",
                ),
            ),
            PublishingStage(
                name="Documentation and reporting",
                owner=self._owner_for("NoteTaker"),
                description="Capture lessons and operational playbooks.",
                channels=channel_names,
                checklist=(
                    "Summarize channel-specific behaviors and escalation contacts.",
                    "Record monitoring dashboards and alert routing for the pipeline.",
                ),
            ),
        ]

        for channel in self._channels:
            stages.append(self._channel_stage(channel))

        return stages

    def as_dict(self) -> Dict[str, object]:
        return {"task": self.task, "stages": [stage.to_dict() for stage in self.build_plan()]}

    def _validate_channels(self) -> None:
        seen_names = set()
        for channel in self._channels:
            channel.validate()
            if channel.name in seen_names:
                raise ValueError(f"Duplicate channel name detected: {channel.name}")
            seen_names.add(channel.name)

    @staticmethod
    def _index_agents(team_config: Sequence[Mapping[str, object]]) -> Dict[str, List[str]]:
        index: Dict[str, List[str]] = {}
        for entry in team_config:
            agent_type = str(entry["type"])
            agent_id = str(entry["id"])
            index.setdefault(agent_type, []).append(agent_id)
        return index

    def _owner_for(self, agent_type: str) -> str:
        if agent_type not in self._agent_index or not self._agent_index[agent_type]:
            raise ValueError(f"No agent configured for type '{agent_type}'")
        return self._agent_index[agent_type][0]

    def _compatibility_checkpoint(self) -> str:
        if self.release_mode == "additive":
            return "Enforce additive delivery so client and backend teams are never blocked."
        return "Highlight breaking changes and secure downstream migration approvals."

    def _channel_stage(self, channel: PublishingChannel) -> PublishingStage:
        checklist: List[str] = [
            f"Prepare publishing contract for {channel.medium} channel '{channel.name}'.",
            f"Verify observability and rollout toggles for {channel.name}.",
        ]
        if channel.requires_client_sync:
            checklist.append("Coordinate rollout sequencing with client-facing teams.")
        if channel.requires_backend_sync:
            checklist.append("Validate backend dependencies remain additive and backward compatible.")
        if channel.notes:
            checklist.append(channel.notes)

        return PublishingStage(
            name=f"Channel rollout: {channel.name}",
            owner=self._owner_for("Developer"),
            description=f"Ship '{self.task}' through {channel.medium} channel '{channel.name}'.",
            channels=(channel.name,),
            checklist=tuple(checklist),
        )
