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
from .storage import CalendarStorage, InMemoryCalendarStorage
from .project import create_meeting, scaffold_project, write_team_config

__all__ = [
    "AgentType",
    "AgentInstance",
    "ParameterSpec",
    "create_meeting",
    "default_agent_types",
    "default_team_config",
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
    "CalendarStorage",
    "InMemoryCalendarStorage",
]
