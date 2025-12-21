import pytest

from bigdaisyswarm.agents import default_team_config
from bigdaisyswarm.publishing import PublishingChannel, PublishingPipeline


def test_publishing_pipeline_builds_stages_with_channels():
    team_config = default_team_config()
    channels = [
        PublishingChannel(
            name="DocsSite",
            medium="web",
            requires_client_sync=True,
            notes="Publish docs without disrupting client delivery.",
        ),
        PublishingChannel(
            name="API",
            medium="api",
            requires_backend_sync=True,
            notes="Supports versioned schema rollout.",
        ),
    ]

    pipeline = PublishingPipeline(
        task="Universal publishing pipeline",
        team_config=team_config,
        channels=channels,
        release_mode="additive",
    )
    stages = pipeline.build_plan()

    assert stages[0].name == "Specification alignment"
    assert stages[0].owner == "ArchitectA"
    assert "additive delivery" in stages[0].checklist[1]

    assert stages[1].name == "Implementation and packaging"
    assert stages[1].owner == "Developer"

    channel_stage = [stage for stage in stages if stage.name == "Channel rollout: DocsSite"][0]
    assert channel_stage.owner == "Developer"
    assert "client-facing teams" in " ".join(channel_stage.checklist)

    api_stage = [stage for stage in stages if stage.name == "Channel rollout: API"][0]
    assert "backend dependencies" in " ".join(api_stage.checklist)
    assert any("versioned schema" in item for item in api_stage.checklist)

    plan_dict = pipeline.as_dict()
    assert plan_dict["task"] == "Universal publishing pipeline"
    assert any(stage["name"] == "Go / No-go" for stage in plan_dict["stages"])


def test_publishing_pipeline_rejects_invalid_inputs():
    team_config = default_team_config()
    valid_channel = PublishingChannel(name="Docs", medium="web")

    with pytest.raises(ValueError):
        PublishingPipeline(task="", team_config=team_config, channels=[valid_channel])

    with pytest.raises(ValueError):
        PublishingPipeline(task="Work", team_config=team_config, channels=[], release_mode="additive")

    with pytest.raises(ValueError):
        PublishingPipeline(
            task="Work",
            team_config=team_config,
            channels=[valid_channel, PublishingChannel(name="Docs", medium="pdf")],
        )

    with pytest.raises(ValueError):
        PublishingPipeline(
            task="Work",
            team_config=team_config,
            channels=[valid_channel],
            release_mode="unsupported",
        )

    broken_team = [entry for entry in team_config if entry["type"] != "Critic"]
    with pytest.raises(ValueError):
        PublishingPipeline(task="Work", team_config=broken_team, channels=[valid_channel])


def test_publishing_channel_validation_and_breaking_mode():
    with pytest.raises(ValueError):
        PublishingChannel(name="", medium="web").validate()

    with pytest.raises(ValueError):
        PublishingChannel(name="Docs", medium="").validate()

    pipeline = PublishingPipeline(
        task="Breaking change",
        team_config=default_team_config(),
        channels=[PublishingChannel(name="Docs", medium="web")],
        release_mode="breaking",
    )
    checklist_item = pipeline.build_plan()[0].checklist[1]
    assert "breaking changes" in checklist_item
