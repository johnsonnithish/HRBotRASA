import re
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ActionSubmitLeaveForm(Action):
    def name(self) -> Text:
        return "submit_leave_form"

    def parse_dates(self, duration_text: str) -> Text:
        if not duration_text:
            return ""

        text = duration_text.strip().lower()

        if text.startswith(("from", "on", "next", "coming", "tomorrow", "day after")):
            return duration_text

        if " to " in text or " - " in text:
            return f"from {duration_text}"

        if "," in text:
            return f"on {duration_text}"

        if "next" in text:
            return f"coming {duration_text}"

        if "tomorrow" in text or "day after" in text:
            return duration_text

        if re.search(r"\b\d+\s+(day|days|week|weeks|month|months)\b", text):
            return f"for {duration_text}"

        return f" {duration_text}"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        reason = tracker.get_slot("reason_leave")
        duration = tracker.get_slot("duration_leave")
        formatted_duration = self.parse_dates(duration)

        message = f"Your leave for '{reason}' {formatted_duration} has been posted!"
        dispatcher.utter_message(text=message)
        dispatcher.utter_message(response="utter_continue_convo")

        return [
            SlotSet("reason_leave", None),
            SlotSet("duration_leave", None)
        ]


class ValidateLeaveForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_leave_form"

    async def validate_duration_leave(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Select longest entity match from latest message
        duration_entities = [
            e for e in tracker.latest_message.get("entities", [])
            if e.get("entity") == "duration_leave" and isinstance(e.get("value"), str)
        ]

        if duration_entities:
            # Select the longest value
            longest = max(duration_entities, key=lambda e: len(e["value"]))
            return {"duration_leave": longest["value"]}

        # Fallback to what Rasa filled if no better match
        return {"duration_leave": slot_value}
