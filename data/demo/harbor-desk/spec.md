# Harbor Desk — baseline product specification

Version: 1.0. Project ID: `harbor-desk`. All organizations, people, conversations and policies in this demo are fictional. This document is the approved baseline, not a collection of new requests. It describes a small equipment reservation portal for the fictional Harbor Desk cooperative. Stable section identifiers are used by the gold cases; a later ingestion step will turn sections into retrievable chunks.

## HD-PURPOSE — Purpose and release boundary

Harbor Desk lends cameras, projectors and portable audio kits to its members. Today coordinators reconcile reservations in a shared spreadsheet and answer availability questions by email. The portal should provide one reliable place to inspect availability, reserve an item and explain why a request cannot be completed. The first release serves one cooperative with a single equipment room and approximately two hundred active members. It does not support multiple organizations, payments, delivery routing or a public marketplace.

The cooperative wants a straightforward browser application. A person should understand whether a reservation succeeded without reading internal logs. Staff should be able to explain access decisions and reservation changes from the visible record. This release replaces reservation bookkeeping, not the cooperative's membership register. Membership verification remains an external administrative process. Names and examples in demonstrations must be invented. Demo records may be reset independently of any future operational deployment.

The application must distinguish availability from a confirmed reservation. Viewing a free slot does not hold it. Confirmation happens only after the server validates permissions, the reservation window and competing bookings. If two members request the same item and overlapping interval, only one request may succeed. The unsuccessful request must explain the conflict and allow the member to choose a different interval.

## HD-ACCESS — Accounts, roles and private access

Every portal page containing equipment availability, reservations or reports requires a signed-in account. Anonymous visitors may see only a sign-in page and a generic description of the cooperative. Public sharing links and anonymous reservation views are excluded from the baseline. A copied reservation URL does not grant access; the server must apply the same authorization checks as ordinary navigation. Invitations create an opportunity to activate an account, not a bypass around authentication.

There are three roles: member, coordinator and administrator. Members can read the equipment catalogue and manage their own reservations. Coordinators can inspect all reservations, confirm equipment handover and send account invitations. Administrators can assign roles, deactivate accounts and configure permitted operational settings. Reports are visible to coordinators and administrators, but export is governed separately by HD-EXPORT. A coordinator may not promote themselves or another person to administrator.

Deactivating an account prevents subsequent sign-ins and new reservations. Existing reservation and audit records remain available to authorized staff. Deactivation must not erase the history that explains an equipment handover. This specification does not define guest, manager or external-collaborator roles. Requests introducing such roles require a clear permission matrix before implementation; the application must not infer permissions from a person's job title.

## HD-INVITES — Invitation workflow

Coordinators and administrators may invite a prospective member by email. An invitation is single-use, expires after seventy-two hours and is tied to the addressed email account. The acceptance page explains whether an invitation is valid, expired or already used. Accepting an expired invitation does not create an account. Staff may issue a replacement invitation, which produces a new token and does not revive an expired token.

The invitation record contains the sender, addressed email, creation time, expiry time and acceptance time when applicable. The portal displays pending and accepted invitations separately. This release does not specify manual revocation of an unexpired invitation, reminder messages for pending invitations or bulk invitation uploads. Those are potential future features rather than implied behavior. An invitation token must not appear in operational logs or exports.

## HD-BOOKING — Reservation rules

Members select one equipment item, a start date and an end date. Reservations use whole calendar days in the cooperative's configured local timezone. A reservation may begin no more than fourteen calendar days after the date of submission. This fourteen-day advance-booking limit applies equally to members, coordinators and administrators. Staff cannot silently bypass it through an alternative form. The maximum reservation duration is three consecutive calendar days, including the start date.

Reservations must not overlap for the same item. A successful reservation receives a stable reference and appears in the member's reservation list. The confirmation page shows the selected item and dates. A declined request does not create a provisional booking or reserve inventory. If the item becomes unavailable before submission, the member sees an actionable availability message. Retrying the same completed submission must not create another reservation.

Members may cancel their own reservation until its start date. Coordinators can cancel any reservation with a required reason. Cancellation releases the reserved interval and records who cancelled it. Recurring reservations, automatic renewal, waiting lists and subscriptions to newly available slots are not included in this baseline. A member who cancels a request is not automatically offered a different item. Recommendations and automatic substitutions require a separate decision about acceptable equipment equivalence.

## HD-CATALOGUE — Equipment information

The catalogue contains an item name, category, plain-language description, storage location and availability calendar. Categories are camera, projector and audio kit. An administrator can mark an item out of service with an explanation. An out-of-service item remains visible with its status, but cannot receive new reservations. Existing affected reservations are flagged for coordinator attention rather than silently cancelled.

Members can filter the catalogue by category and requested dates. The default view shows active items alphabetically. Search matches item names without case sensitivity. The baseline does not persist personal filter presets between visits. There are no equipment ratings, comments, image uploads or recommendation algorithms. Staff can update descriptive text, but inventory identifiers remain stable so that older reservations continue to reference the same physical item.

## HD-REPORTS — Reservation reporting

Coordinators and administrators can view a reservation report filtered by date interval, item and reservation status. Each row contains the reservation reference, item name, requested dates and status. Member names are visible only to staff with reporting access. Members can view their own reservation list but not the organization-wide report. Empty reports show a clear empty state rather than an error.

The report is generated on demand from current records. The baseline does not schedule reports, email attachments or save personal report views. Counts shown above the report must use the same filters as the displayed rows. Changing a filter and then exporting must not silently export an older filter selection. The interface should make the active filters visible so a staff member can explain what a report represents.

## HD-EXPORT — Report export permissions and format

Only administrators may export reservation reports. Coordinators may view reports but may not download them. The server must enforce this restriction even when a coordinator sends an export request directly. Hiding the export button alone is insufficient. Members have no report export permission. Introducing another role with export permission is a change to the approved access policy, not a clarification of the existing behavior.

The initial export format is CSV encoded as UTF-8. Exported rows follow the active report filters and contain the same approved columns as the report. CSV values that could be interpreted as spreadsheet formulas must be rendered safely. The filename includes the export date and does not contain a member's name. PDF, spreadsheet workbooks, scheduled delivery and a new monthly summary column are outside the baseline. Large reports may take time to prepare, but no asynchronous export queue is specified for the first release.

## HD-AUDIT — Audit history and retention

Role changes, reservation creation, cancellation and handover confirmation create audit events. Each event records an actor identifier, action, affected record identifier and timestamp. Audit records are append-only: ordinary users, coordinators and administrators cannot edit earlier events through the portal. Corrections are represented by a new event referencing the affected action. Passwords, invitation tokens and session tokens must never be recorded in audit data.

Audit events are retained for one hundred eighty days. A daily cleanup removes events older than that retention period. Administrators can view audit history for a particular affected record, but the baseline does not include a general actor filter or a free-text search across all events. Retaining audit data for a longer period changes the approved retention policy and requires explicit approval. Exporting report rows must not accidentally include audit payloads or account credentials.

The retention rule concerns audit events rather than active reservations. Removing an old audit event does not delete a current booking. Before changing retention, stakeholders must identify both the purpose of longer storage and the records it covers. A vague request to keep everything must not be interpreted as permission for indefinite retention.

## HD-NOTIFY — Notifications

The portal sends email confirmations for accepted reservations and cancellations. Invitation emails are also part of the invitation workflow. Messages include a reservation reference where applicable and a link back to the authenticated portal. Notification failures do not roll back an otherwise valid reservation; the interface must still show the confirmed result. Staff can inspect whether delivery was attempted without seeing provider credentials.

SMS, push notifications and messaging-app integrations are outside the first release. A request to use email instead of SMS restates the baseline rather than adding a second delivery channel. This specification does not include waitlist notifications, pending-invitation reminders or scheduled report email. A new notification must identify its triggering event, recipient and any opt-out behavior before it becomes an implementation-ready story.

## HD-USABILITY — Accessibility and interaction

Core reservation and reporting actions must be usable with a keyboard. Inputs have visible labels, focus remains visible and status is not communicated by color alone. Validation errors identify the affected field and explain how to correct it. After a failed submission, entered values remain in the form unless retaining a sensitive value would be inappropriate. Dates use an unambiguous display format and identify the cooperative's timezone where confusion is possible.

The supported viewport range is from a narrow mobile browser to a desktop browser. Tables may use a compact layout on smaller screens but cannot hide the reservation reference or status. No custom design system, animation framework or native mobile application is required. The baseline has no numeric response-time target, so phrases such as fast, instant or smooth require measurable clarification. Accessibility is part of the release criteria rather than optional visual polish.

## HD-OPERATIONS — Reliability and support

Transient outbound email failures with HTTP status 429 or 5xx are retried at most three times after the initial attempt, using exponential backoff. Permanent client errors are not retried automatically. Each delivery attempt must be distinguishable in operational logs without logging message content that contains secrets. Duplicate delivery attempts must not create duplicate reservation records. Operators should be able to associate a failure with a reservation reference.

The baseline includes an internal health endpoint for service availability but no publicly accessible system-status page. Monitoring scope, alert recipients and numeric availability objectives remain undecided. There is no approved maintenance schedule or restriction on weekend schema migrations. A request for monitoring everything needs clarification of the events, thresholds and response owner. A health response alone does not prove that an external email provider or every database query is working.

## HD-ACCEPTANCE — Baseline acceptance

Acceptance uses invented member accounts and equipment records. A member signs in, finds a free interval within fourteen days, confirms a reservation and sees its reference. A second overlapping request is rejected without a duplicate booking. A coordinator can inspect the report and cannot export it; an administrator can export a filtered CSV. An anonymous browser cannot view a copied private reservation link.

The test set must also cover cancellation, expired invitations, out-of-service equipment, audit append-only behavior and keyboard interaction. New discovery requests are classified against this baseline as new, duplicate, conflict or unclear. A conflict is not automatically approved by appearing in a transcript. Staff must review the supporting quote, the baseline section and the open question before treating a policy change as agreed scope.
