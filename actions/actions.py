import re
import json
import os
from dateparser import parse
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from datetime import datetime

def normalize_year(date_obj):
    if date_obj and date_obj.year < 2000:
        return date_obj.replace(year=datetime.now().year)
    return date_obj


leave_file= "store_leave.json"
def load_leave_data():
    if os.path.exists(leave_file):
        with open(leave_file, "r") as f:
            return json.load(f)
    return {}

def save_leave_data(data):
    with open(leave_file, "w") as f:
        json.dump(data, f, indent=2)

def add_leave(sender_id, start, end):
    data = load_leave_data()
    user_leaves = data.get(sender_id, [])
    user_leaves.append({
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d")
    })
    data[sender_id] = user_leaves
    save_leave_data(data)

def check_overlap(sender_id, new_start, new_end):

    data = load_leave_data()
    for leave in data.get(sender_id, []):
        start = normalize_year(parse(leave["start"]))
        end = normalize_year(parse(leave["end"]))
        if new_start <= end and new_end >= start:
            return True
    return False

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
        sender_id = tracker.sender_id

        try:
            text = formatted_duration.lower().replace("from", "").strip()
            parts = text.split("to")
            if len(parts) == 2:
                start_date = normalize_year(parse(parts[0].strip()))
                end_date = normalize_year(parse(parts[1].strip())) if len(parts) == 2 else start_date
            else:
                start_date = end_date = parse(text.strip())
            if not start_date or not end_date:
                raise ValueError("Invalid date format")

            if start_date > end_date:
                raise ValueError("Start date cannot be after end date")

            if check_overlap(sender_id, start_date, end_date):
                dispatcher.utter_message(text="You already have a leave scheduled during this time.")
                return []

            add_leave(sender_id, start_date, end_date)
            message = f"Your leave for '{reason}' {formatted_duration} has been posted!"
            dispatcher.utter_message(text=message)
            dispatcher.utter_message(response="utter_continue_convo")

        except ValueError as e:
            dispatcher.utter_message(text=f"Error processing your leave request: {str(e)}")
            return []

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
        duration_entities = [
            e for e in tracker.latest_message.get("entities", [])
            if e.get("entity") == "duration_leave" and isinstance(e.get("value"), str)
        ]

        if duration_entities:
            longest = max(duration_entities, key=lambda e: len(e["value"]))
            return {"duration_leave": longest["value"]}
        return {"duration_leave": slot_value}
