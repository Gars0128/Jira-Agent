# Harbor Desk discovery 02 — Audit review

Mira (analyst): Your microphone is much clearer today. Are we still reviewing audit history rather than reservation history?
Eli (administrator): Exactly. The reservations themselves are not what I want to delete. I am talking about the log of who changed things.
Mira (analyst): The baseline keeps audit events for one hundred eighty days and removes older events daily.
Eli (administrator): Keep audit events for three hundred sixty-five days instead of one hundred eighty days.
Mira (analyst): That is a change to the retention policy. Is a reason or approval recorded yet?
Eli (administrator): Not yet. I need the committee to approve it. Our annual review is the reason, but do not tell the developers it is already signed off.
Nora (cooperative lead): I was about to say keep them forever, but that is too broad. Withdraw forever. The proposed change is one year, subject to that review.
Mira (analyst): Understood. What should remain unchanged?
Eli (administrator): Audit events must remain append-only; corrections should create a new event.
Mira (analyst): That matches the specification. How do you find the entry you need?
Eli (administrator): Today I have to open a record first. Allow administrators to filter audit history by actor identifier.
Mira (analyst): We can describe an exact actor filter. Do you also need free-text search?
Eli (administrator): No, not in this change. I said search earlier in the week, but I only need the actor identifier filter. One value at a time is enough.
Nora (cooperative lead): Can you get it to us soon?
Mira (analyst): Soon is not a delivery date. Do you have a deadline linked to the review?
Nora (cooperative lead): I do not have the committee date yet. Put that on the question list; please do not manufacture a date from the annual-review wording.
Eli (administrator): Also, none of this should put invitation tokens into the audit log. I know that is already prohibited. I just wanted to make sure the new filter does not change the recorded data.
Mira (analyst): We will keep the policy change, the new filter and the scheduling question separate. Thanks, and I hope the microphone survives the rest of the afternoon.
