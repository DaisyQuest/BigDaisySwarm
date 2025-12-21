"""Big Daisy Swarm agent coordination toolkit."""

from .agents import (
    AgentType,
    AgentInstance,
    ParameterSpec,
    default_agent_types,
    default_team_config,
    validate_team_config,
)
from .calendar import (
    CalendarError,
    CalendarService,
    DSLExecutor,
    Event,
    EventService,
    Participant,
    ParticipantService,
)
from .project import create_meeting, scaffold_project, write_team_config
from .project import kickoff_task, latest_meeting_path, list_meetings, plan_next_meeting

__all__ = [
    "AgentType",
    "AgentInstance",
    "ParameterSpec",
    "create_meeting",
    "default_agent_types",
    "default_team_config",
    "kickoff_task",
    "latest_meeting_path",
    "list_meetings",
    "plan_next_meeting",
    "scaffold_project",
    "validate_team_config",
    "write_team_config",
    "CalendarError",
    "CalendarService",
    "DSLExecutor",
    "Event",
    "EventService",
    "Participant",
    "ParticipantService",
]
