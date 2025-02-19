from enum import Enum

from kairon.shared.data.constant import ACCESS_ROLES

DEFAULT_INTENTS = {'restart', 'back', 'out_of_scope', 'session_start', 'nlu_fallback'}

DEFAULT_ACTIONS = {'action_listen', 'action_restart', 'action_session_start', 'action_default_fallback',
                   'action_deactivate_loop', 'action_revert_fallback_events', 'action_default_ask_affirmation',
                   'action_default_ask_rephrase', 'action_two_stage_fallback', 'action_back', '...'}

SYSTEM_TRIGGERED_UTTERANCES = {'utter_default', 'utter_please_rephrase'}

ADMIN_ACCESS = [ACCESS_ROLES.ADMIN.value]

DESIGNER_ACCESS = [ACCESS_ROLES.ADMIN.value, ACCESS_ROLES.DESIGNER.value]

TESTER_ACCESS = [ACCESS_ROLES.ADMIN.value, ACCESS_ROLES.DESIGNER.value, ACCESS_ROLES.TESTER.value]


class SLOT_SET_TYPE(str, Enum):
    FROM_VALUE = "from_value"
    RESET_SLOT = "reset_slot"


class SSO_TYPES(str, Enum):
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    GOOGLE = "google"
