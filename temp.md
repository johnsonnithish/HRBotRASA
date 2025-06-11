import dateparser
from datetime import datetime, timedelta

leave_history = []  # Store tuples like (start_date, end_date)

class ActionSubmitLeaveForm(Action):
    def name(self) -> Text:
        return "submit_leave_form"

    def parse_dates(self, duration_text: str) -> Tuple[datetime, datetime]:
        # Basic parsing for ranges like "Jan 6 to Jan 9"
        parts = duration_text.lower().replace("from ", "").split("to")
        if len(parts) == 2:
            start = dateparser.parse(parts[0].strip())
            end = dateparser.parse(parts[1].strip())
        else:
            start = end = dateparser.parse(duration_text.strip())
        return start, end

    def is_overlapping(self, start: datetime, end: datetime) -> bool:
        for prev_start, prev_end in leave_history:
            if start <= prev_end and end >= prev_start:
                return True
        return False

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        reason = tracker.get_slot("reason_leave")
        duration = tracker.get_slot("duration_leave")

        try:
            start, end = self.parse_dates(duration)
        except:
            dispatcher.utter_message(text="Sorry, I couldn't understand the leave dates.")
            return [SlotSet("reason_leave", None), SlotSet("duration_leave", None)]

        # Check for overlapping leaves
        if self.is_overlapping(start, end):
            dispatcher.utter_message(
                text=f"Your leave from {start.strftime('%b %d')} to {end.strftime('%b %d')} overlaps with an existing leave. Please choose different dates."
            )
            return [SlotSet("reason_leave", None), SlotSet("duration_leave", None)]

        # Save leave if no conflict
        leave_history.append((start, end))      

        dispatcher.utter_message(
            text=f"Your leave for '{reason}' from {start.strftime('%b %d')} to {end.strftime('%b %d')} has been posted!"
        )
        dispatcher.utter_message(response="utter_continue_convo")

        return [SlotSet("reason_leave", None), SlotSet("duration_leave", None)]
