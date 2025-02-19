from enum import Enum

KAIRON_ACTION_RESPONSE_SLOT = "KAIRON_ACTION_RESPONSE"


class ParameterType(str, Enum):
    user = "user"
    action = "action"
    form = "form"
    http = "http"
    http_action_config = "http_action_config"


class ActionParameterType(str, Enum):
    value = "value"
    slot = "slot"
    sender_id = "sender_id"
    user_message = "user_message"
    intent = "intent"
    chat_log = "chat_log"


class ActionType(str, Enum):
    http_action = "http_action"
    slot_set_action = "slot_set_action"
    form_validation_action = "form_validation_action"
    email_action = "email_action"
    google_search_action = "google_search_action"


class LogicalOperators(str, Enum):
    and_operator = "and"
    or_operator = "or"
    not_operator = "not"


class SlotValidationOperators(str, Enum):
    equal_to = "=="
    not_equal_to = "!="
    is_greater_than = ">"
    is_less_than = "<"
    case_insensitive_equals = "case_insensitive_equals"
    contains = "contains"
    is_in = "in"
    is_not_in = "not in"
    starts_with = "startswith"
    ends_with = "endswith"
    has_length = "has_length"
    has_length_greater_than = "has_length_greater_than"
    has_length_less_than = "has_length_less_than"
    has_no_whitespace = "has_no_whitespace"
    is_an_email_address = "is_an_email_address"
    matches_regex = "matches_regex"
    is_true = "is_true"
    is_false = "is_false"
    is_null_or_empty = "is_null_or_empty"
    is_not_null_or_empty = "is_not_null_or_empty"
