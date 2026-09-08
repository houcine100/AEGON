# tests/test_alarm.py
# Isolation + stub tests for the alarm connector.
# Run: python -m tests.test_alarm
#
# Isolation smoke test (before enabling):
#   python -c "from tools.alarm.alarm_tool import AlarmConnector; \
#              print(AlarmConnector().execute({}))"
#
# Full-chain test (after enabling):
#   Run the orchestrator and ask a natural-language trigger, e.g.:
#   "TODO: describe the trigger phrase here"

from tools.alarm.alarm_tool import AlarmConnector


def test_validate_accepts_empty_dict():
    assert AlarmConnector().validate({}) is True


def test_execute_raises_until_implemented():
    try:
        AlarmConnector().execute({})
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass  # expected — fill in execute() first


if __name__ == "__main__":
    test_validate_accepts_empty_dict()
    test_execute_raises_until_implemented()
    print("Stub tests pass. Implement the connector then re-run, Sir.")
