import pytest
from app.services.ai_service import AIService

@pytest.fixture
def ai_service():
    return AIService()

def test_repair_json_valid(ai_service):
    json_str = '{"key": "value"}'
    assert ai_service._repair_json(json_str) == json_str

def test_repair_json_truncated_string(ai_service):
    json_str = '{"key": "value'
    repaired = ai_service._repair_json(json_str)
    assert repaired == '{"key": "value"}'

def test_repair_json_truncated_array(ai_service):
    json_str = '{"key": ["a", "b"'
    repaired = ai_service._repair_json(json_str)
    assert repaired == '{"key": ["a", "b"]}'

def test_repair_json_truncated_object(ai_service):
    json_str = '{"key": {"inner": "val"'
    repaired = ai_service._repair_json(json_str)
    assert repaired == '{"key": {"inner": "val"}}'

def test_repair_json_trailing_comma(ai_service):
    json_str = '{"key": "val",'
    repaired = ai_service._repair_json(json_str)
    assert repaired == '{"key": "val"}'

def test_repair_json_nested_complex(ai_service):
    json_str = '{"segments": [{"id": 1, "text": "hello'
    repaired = ai_service._repair_json(json_str)
    assert repaired == '{"segments": [{"id": 1, "text": "hello"}]}'

def test_repair_json_mid_key(ai_service):
    json_str = '{"segments": [{"id": 1, "te'
    repaired = ai_service._repair_json(json_str)
    # The current logic strips incomplete keys for validity, which is acceptable
    assert repaired == '{"segments": [{"id": 1}]}'
