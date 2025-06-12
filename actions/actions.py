import re
import json
import os
from dateparser import parse
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop
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

def add_leave(sender_id, start, end, reason):
    data = load_leave_data()
    user_leaves = data.get(sender_id, [])
    user_leaves.append({
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "reason": reason
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
        confirm = tracker.get_slot("confirm_leave")
        reason = tracker.get_slot("reason_leave")
        duration = tracker.get_slot("duration_leave")
        formatted_duration = self.parse_dates(duration)
        sender_id = tracker.sender_id

        if confirm:
            try:
                text = formatted_duration.lower().replace("from", "").strip()
                parts = text.split("to")
                if len(parts) == 2:
                    start_date = normalize_year(parse(parts[0].strip()))
                    end_date = normalize_year(parse(parts[1].strip())) if len(parts) == 2 else start_date
                else:
                    start_date = end_date = parse(text.strip())
                
                add_leave(sender_id, start_date, end_date, reason)
                message = f"Your leave for '{reason}' {formatted_duration} has been posted!"
                dispatcher.utter_message(text=message)
                dispatcher.utter_message(response="utter_continue_convo")

            except ValueError as e:
                dispatcher.utter_message(text=f"Error processing your leave request: {str(e)}")
                return []

            return [
                SlotSet("reason_leave", None),
                SlotSet("duration_leave", None),
                SlotSet("confirm_leave", None)
            ]
        else:
            dispatcher.utter_message(text="Let's update your leave request.")
            if not reason or not duration:
                return [SlotSet("confirm_leave", None)]
            return [
                SlotSet("duration_leave", None),
                SlotSet("reason_leave", None),
                SlotSet("confirm_leave", None),
                ActiveLoop("leave_form")
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
        from dateparser import parse

        sender_id = tracker.sender_id

        duration_entities = [
            e for e in tracker.latest_message.get("entities", [])
            if e.get("entity") == "duration_leave" and isinstance(e.get("value"), str)
        ]

        if duration_entities:
            slot_value = max(duration_entities, key=lambda e: len(e["value"]))["value"]

        duration_text = slot_value.lower().replace("from", "").strip()
        parts = duration_text.split("to")

        try:
            if len(parts) == 2:
                start = normalize_year(parse(parts[0].strip()))
                end = normalize_year(parse(parts[1].strip()))
            else:
                start = end = normalize_year(parse(duration_text.strip()))

            if not start or not end:
                raise ValueError("Invalid date format")

            if start > end:
                dispatcher.utter_message(text="The start date cannot be after the end date.")
                return {"duration_leave": None}

            if check_overlap(sender_id, start, end):
                dispatcher.utter_message(text="That duration overlaps with an existing leave. Please choose different dates.")
                return {"duration_leave": None}

            return {"duration_leave": slot_value}

        except Exception as e:
            dispatcher.utter_message(text="I couldn't understand that leave duration. Please rephrase.")
            return {"duration_leave": None}

