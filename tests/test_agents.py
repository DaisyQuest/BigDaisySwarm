import pytest

from bigdaisyswarm.agents import AgentType, ParameterSpec, default_agent_types, default_team_config, validate_team_config


def test_default_agent_types_include_all_roles():
    agent_types = default_agent_types()
    names = {agent_type.name for agent_type in agent_types}
    assert names == {
        "Architect",
        "Developer",
        "TestEngineer",
        "Critic",
        "NoteTaker",
        "Arbiter",
    }

    architect = next(agent for agent in agent_types if agent.name == "Architect")
    assert {param.name for param in architect.parameters} == {
        "preferSimplicityLevel",
        "preferHomebakedCodeLevel",
    }


def test_validate_team_config_accepts_defaults():
    team_config = default_team_config()
    # Should not raise
    validate_team_config(team_config)


@pytest.mark.parametrize("missing_agent_type", ["Critic", "Developer"])
def test_validate_team_config_rejects_missing_agent_type(missing_agent_type):
    team_config = [
        entry for entry in default_team_config() if entry["type"] != missing_agent_type
    ]

    with pytest.raises(ValueError) as excinfo:
        validate_team_config(team_config)

    assert "Missing required agent types" in str(excinfo.value)


def test_validate_team_config_rejects_unknown_agent():
    team_config = default_team_config()
    team_config.append({"id": "Shadow", "type": "Unknown", "parameters": {}})

    with pytest.raises(ValueError) as excinfo:
        validate_team_config(team_config)

    assert "Unknown agent types" in str(excinfo.value)


def test_validate_team_config_rejects_out_of_bounds_value():
    team_config = default_team_config()
    team_config[0]["parameters"]["preferSimplicityLevel"] = 2.0

    with pytest.raises(ValueError) as excinfo:
        validate_team_config(team_config)

    assert "preferSimplicityLevel" in str(excinfo.value)


def test_validate_team_config_rejects_unknown_parameter():
    team_config = default_team_config()
    team_config[0]["parameters"]["unexpected"] = 0.1

    with pytest.raises(ValueError) as excinfo:
        validate_team_config(team_config)

    assert "unknown parameters" in str(excinfo.value)


def test_validate_team_config_rejects_missing_parameter():
    team_config = default_team_config()
    team_config[0]["parameters"].pop("preferSimplicityLevel")

    with pytest.raises(ValueError) as excinfo:
        validate_team_config(team_config)

    assert "missing parameter" in str(excinfo.value)


def test_default_team_config_requires_parameter_defaults():
    agent_without_default = AgentType(
        name="Custom",
        description="",
        parameters=[ParameterSpec(name="value", param_type="double")],
    )

    with pytest.raises(ValueError) as excinfo:
        default_team_config(default_agent_types() + [agent_without_default])

    assert "No default value provided" in str(excinfo.value)


def test_validate_team_config_rejects_boolean_parameter_value():
    team_config = default_team_config()
    team_config[0]["parameters"]["preferSimplicityLevel"] = True

    with pytest.raises(ValueError) as excinfo:
        validate_team_config(team_config)

    assert "must be numeric" in str(excinfo.value)


def test_validate_team_config_rejects_duplicate_ids():
    team_config = default_team_config()
    team_config.append(
        {"id": team_config[0]["id"], "type": "Developer", "parameters": {"preferSimplicityLevel": 0.5, "preferHomebakedCodeLevel": 0.5}}
    )

    with pytest.raises(ValueError) as excinfo:
        validate_team_config(team_config)

    assert "Duplicate agent id" in str(excinfo.value)


def test_validate_team_config_requires_list():
    with pytest.raises(ValueError) as excinfo:
        validate_team_config({})

    assert "must be a list" in str(excinfo.value)


def test_validate_team_config_requires_fields():
    with pytest.raises(ValueError) as excinfo:
        validate_team_config([{"type": "Architect", "parameters": {}}])

    assert "Missing required fields" in str(excinfo.value)
