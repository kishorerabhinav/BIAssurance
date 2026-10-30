import pytest

from biwb.config import load_settings


def test_defaults_keep_ai_disabled():
    s = load_settings({}, use_dotenv=False)
    assert s.ai_enabled is False
    assert s.ai_model == "claude-opus-5-5"
    assert s.ai_effort == "medium"
    assert s.app_db_path.name == "app.db"


def test_ai_flag_and_model_are_configurable():
    s = load_settings(
        {"BIWB_AI_ENABLED": "true", "BIWB_AI_MODEL": "claude-sonnet-5-5", "BIWB_AI_EFFORT": "low"},
        use_dotenv=False,
    )
    assert s.ai_enabled is True
    assert s.ai_model == "claude-sonnet-5-5"
    assert s.ai_effort == "low"


@pytest.mark.parametrize("env", [{"BIWB_AI_EFFORT": "extreme"}, {"BIWB_AI_MODEL": "  "}])
def test_invalid_values_fail_loudly(env):
    with pytest.raises(ValueError):
        load_settings(env, use_dotenv=False)


def test_settings_never_hold_api_key():
    s = load_settings({"ANTHROPIC_API_KEY": "sk-test-not-real"}, use_dotenv=False)
    assert "sk-test" not in repr(s)
