from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

AGENTS = ["Maria", "James", "Priya", "David", "Sarah", "Alex", "Nina", "Carlos"]
DATES = [
    "March 12th",
    "April 3rd",
    "May 18th",
    "June 7th",
    "July 22nd",
    "August 9th",
    "September 14th",
    "October 2nd",
]
AMOUNTS = ["$29.99", "$49.99", "$79.99", "$99.00", "$149.50", "$199.00"]
ORDER_IDS = ["ORD-48291", "ORD-77304", "ORD-55102", "ORD-91837", "ORD-66420", "ORD-33018"]


def _pick(options: list[str], index: int) -> str:
    return options[index % len(options)]


def _billing_complaint(index: int) -> str:
    agent_date = _pick(DATES, index)
    amount = _pick(AMOUNTS, index)
    order_id = _pick(ORDER_IDS, index)
    return (
        f"A customer contacted support on {agent_date} regarding a billing issue that had been escalating "
        f"over the past three weeks. They noticed duplicate charges of {amount} appearing on consecutive "
        f"monthly invoices despite having canceled an add-on service earlier in the quarter. The customer "
        f"explained they had already opened two previous tickets through the online portal and waited over "
        f"ten business days without receiving a substantive update from the billing team. According to their "
        f"account notes tied to order {order_id}, they attempted to resolve the matter through live chat "
        f"twice but were disconnected both times before reaching an agent who could review the invoice history. "
        f"The overcharge affected their monthly household budget and created anxiety about whether their "
        f"payment method was being compromised or incorrectly stored in the billing system. They expressed "
        f"frustration that automated emails promised a resolution within seventy-two hours but no credit memo "
        f"or corrected invoice ever arrived in their inbox or account dashboard. The customer asked for a full "
        f"refund of the duplicate charges, written confirmation that the add-on was removed permanently from "
        f"their subscription profile, and assurance that future billing cycles would reflect the correct tier. "
        f"They made it clear they were considering switching providers if the billing errors continued and "
        f"requested escalation to a billing specialist rather than receiving another generic template response."
    )


def _billing_solution(index: int) -> str:
    agent = _pick(AGENTS, index)
    amount = _pick(AMOUNTS, index)
    order_id = _pick(ORDER_IDS, index)
    return (
        f"Support agent {agent} reviewed the customer's billing history across the last six invoice cycles "
        f"and identified that an add-on service cancellation was never propagated to the recurring billing "
        f"engine. She confirmed the duplicate {amount} charges on recent statements and initiated a manual "
        f"credit adjustment totaling twice that amount to cover both billing periods affected by the error. "
        f"{agent} contacted the billing operations team to verify that the add-on SKU was removed from the "
        f"subscription profile linked to {order_id} and added a permanent account flag to prevent reactivation "
        f"without explicit customer consent. She called the customer within two hours of case assignment, "
        f"walked through the line-item breakdown on each invoice, and sent a follow-up email summarizing the "
        f"investigation findings and remediation steps taken on their account. The refund was processed to the "
        f"original payment method and the customer received an automated confirmation showing an expected "
        f"posting date of three to five business days depending on their card issuer. {agent} also applied a "
        f"one-time courtesy credit for the delays in prior support interactions and documented the case in the "
        f"CRM with a root-cause tag for the billing sync failure. A supervisor review was scheduled to audit "
        f"similar accounts affected by the same cancellation sync bug. The customer acknowledged receipt of the "
        f"resolution email and confirmed they would monitor the next billing cycle before formally closing the ticket."
    )


def _delivery_complaint(index: int) -> str:
    order_id = _pick(ORDER_IDS, index)
    agent_date = _pick(DATES, index + 1)
    return (
        f"A customer reached out on {agent_date} because a priority shipment associated with order {order_id} "
        f"had not arrived after the guaranteed delivery window expired by four full business days. The package "
        f"contained time-sensitive equipment needed for a client presentation scheduled later that week, and the "
        f"tracking page had shown the same in-transit status without location updates for seventy-two hours. "
        f"The customer stated they had already contacted the carrier directly and was told the handoff to the "
        f"local delivery partner was delayed due to a warehouse sorting backlog, but no revised delivery date "
        f"was provided. They explained that missing the delivery forced them to rent substitute equipment at "
        f"additional cost and damaged their credibility with an important client who was waiting on the shipment. "
        f"Prior to opening this ticket, the customer checked their account notification settings and confirmed "
        f"delivery alerts were enabled, yet they received no proactive message when the shipment stalled. They "
        f"requested immediate confirmation of the package location, expedited redelivery at no charge, and "
        f"compensation for the rental fees they incurred because of the delay. The customer also asked whether "
        f"their address had been entered incorrectly during checkout and wanted written assurance that future "
        f"orders would not encounter the same routing failure on this delivery route."
    )


def _delivery_solution(index: int) -> str:
    agent = _pick(AGENTS, index + 1)
    order_id = _pick(ORDER_IDS, index + 1)
    return (
        f"Support agent {agent} opened an internal logistics trace for order {order_id} and confirmed the "
        f"shipment was delayed at a regional sort facility rather than lost in transit. He coordinated with "
        f"the fulfillment partner to re-route the package onto an expedited lane and issued a replacement "
        f"authorization in parallel so the customer would receive goods even if the original carton could not "
        f"be recovered in time. {agent} provided the customer with a live tracking link, a direct warehouse "
        f"contact for status checks, and a written timeline showing expected delivery within forty-eight hours. "
        f"He waived all shipping fees on the reshipment and applied a service credit reflecting the rental "
        f"expense the customer documented with receipts attached to the case. The customer received proactive "
        f"SMS and email updates at each transit milestone until the replacement package was signed for at their "
        f"office. {agent} logged a carrier performance incident, flagged the account for priority handling on "
        f"future orders, and added a delivery-instruction note to reduce misroutes on repeat purchases. After "
        f"delivery, he followed up by phone to confirm the equipment worked as expected and sent a closure "
        f"summary outlining the corrective actions taken. The customer accepted the resolution and agreed to "
        f"monitor one additional order before deciding whether further escalation to executive support was needed."
    )


def _product_complaint(index: int) -> str:
    order_id = _pick(ORDER_IDS, index + 2)
    agent_date = _pick(DATES, index + 2)
    return (
        f"A customer reported on {agent_date} that a product purchased under order {order_id} arrived with "
        f"a critical defect that made it unusable for its intended purpose. They described visible damage to "
        f"the housing, intermittent power failures during normal operation, and error codes that appeared "
        f"within minutes of first setup despite following the included quick-start guide exactly. The customer "
        f"had purchased the item for daily professional use and emphasized that downtime was costing them billable "
        f"hours because no backup unit was available in their home office. They attempted basic troubleshooting "
        f"steps from the help center, including firmware updates and factory reset procedures, but the device "
        f"continued to fail during the same diagnostic sequence each time. Photos and a short screen recording "
        f"were uploaded to the original ticket, yet the customer received only an auto-reply asking them to wait "
        f"for a technician review that never materialized over five business days. They requested a warranty "
        f"replacement shipped immediately, prepaid return instructions for the defective unit, and confirmation "
        f"that the replacement would be inspected before dispatch to avoid receiving another faulty item. The "
        f"customer also asked whether a known quality issue existed for this batch and wanted transparency about "
        f"how the company would prevent a repeat failure on the replacement shipment."
    )


def _product_solution(index: int) -> str:
    agent = _pick(AGENTS, index + 2)
    order_id = _pick(ORDER_IDS, index + 2)
    return (
        f"Support agent {agent} reviewed the customer's photo evidence and escalated the case to the product "
        f"quality team for batch-level analysis on order {order_id}. Quality engineering confirmed the symptoms "
        f"matched a known manufacturing variance and authorized an advanced replacement under warranty without "
        f"requiring the customer to wait for the defective unit to arrive at the repair center first. {agent} "
        f"arranged overnight shipping for the replacement, emailed a prepaid return label valid for thirty days, "
        f"and added a QA hold note so the new unit underwent an outbound inspection before leaving the warehouse. "
        f"She called the customer to explain the root cause in plain language, outlined the return process, and "
        f"provided a direct extension for updates until delivery was confirmed. When the replacement arrived, "
        f"{agent} scheduled a follow-up check-in to verify setup succeeded and documented the resolution under "
        f"a warranty exception code tied to the batch review. The customer confirmed the replacement operated "
        f"correctly through a full workday and shared positive feedback about the speed of the exchange process. "
        f"{agent} closed the loop with the quality team so inventory from the affected batch was quarantined "
        f"and future shipments were sourced from a verified alternate supplier. A satisfaction survey was sent "
        f"after closure and the case was marked resolved with a preventative action record for leadership review."
    )


def _subscription_complaint(index: int) -> str:
    agent_date = _pick(DATES, index + 3)
    amount = _pick(AMOUNTS, index + 1)
    return (
        f"A customer submitted a detailed complaint on {agent_date} after attempting to cancel their premium "
        f"subscription through both the mobile app and the account settings page without success. Each cancellation "
        f"attempt appeared to complete with an on-screen confirmation, yet the subscription remained active and "
        f"a renewal charge of {amount} posted to their card the following morning. The customer contacted support "
        f"by phone earlier in the month and was told the account had been canceled, but billing records showed "
        f"no cancellation event and the service tier never changed in the admin portal view they were shown. "
        f"They expressed concern about being charged for a plan they no longer used and frustration that prior "
        f"support interactions did not match the actual account state. The customer also noted that promotional "
        f"emails continued after the alleged cancellation, suggesting their preferences were not updated correctly. "
        f"They requested immediate cancellation with written proof, a full refund of the most recent renewal, "
        f"and deletion of stored payment details to prevent further accidental charges. Additionally, they asked "
        f"for an explanation of why self-service cancellation failed repeatedly and wanted assurance that the "
        f"account would not be reactivated without their explicit consent during any future promotional campaigns."
    )


def _subscription_solution(index: int) -> str:
    agent = _pick(AGENTS, index + 3)
    amount = _pick(AMOUNTS, index + 1)
    return (
        f"Support agent {agent} audited the customer's subscription lifecycle events and found that cancellation "
        f"requests from the app were failing silently due to a stale session token that never refreshed after a "
        f"password reset. He manually canceled the active plan, revoked upcoming renewal authorization, and "
        f"processed a full refund of {amount} for the erroneous charge that posted after the customer's last "
        f"documented cancellation attempt. {agent} removed the stored payment method at the customer's request, "
        f"disabled marketing emails tied to the premium tier, and sent a formal cancellation confirmation letter "
        f"with effective date, refund reference number, and instructions for exporting any remaining account data. "
        f"He opened an engineering ticket to fix the session refresh bug affecting mobile cancellations and linked "
        f"the customer's case as a reference example for QA validation. The customer was offered a courtesy service "
        f"credit usable on a future purchase even though they had chosen not to continue the subscription. {agent} "
        f"called back within twenty-four hours to confirm no further charges appeared and that account access "
        f"reflected the downgraded free tier correctly. He documented each step in the CRM timeline and flagged "
        f"the profile for manual review if any billing activity resumed within the next two billing cycles. The "
        f"customer confirmed the refund notification and accepted the written cancellation proof as sufficient "
        f"resolution pending the engineering fix rollout announced for the following sprint."
    )


def _support_complaint(index: int) -> str:
    agent_date = _pick(DATES, index + 4)
    order_id = _pick(ORDER_IDS, index + 3)
    return (
        f"A customer escalated a case on {agent_date} because they had been waiting more than nine business days "
        f"for a substantive response on a urgent issue linked to order {order_id}. They had opened the original "
        f"ticket through email, received an automated acknowledgment, and then heard nothing despite two polite "
        f"follow-up messages that included additional documentation requested in the first reply. The customer "
        f"described feeling deprioritized because social media channels appeared to receive faster public responses "
        f"than their private support thread, even though their issue involved active service disruption. They "
        f"explained the delay forced them to pause a team project and allocate internal resources to work around "
        f"the unresolved problem while still paying for the affected service tier. Prior attempts to use the "
        f"priority chat option resulted in queue times exceeding forty minutes on multiple occasions before they "
        f"abandoned the session. The customer requested assignment to a dedicated agent, a same-day callback, "
        f"and a clear action plan with milestones rather than another generic holding message. They also asked "
        f"for transparency about why response-time targets were missed and whether their account had been routed "
        f"to an incorrect support queue based on the product category selected during ticket creation."
    )


def _support_solution(index: int) -> str:
    agent = _pick(AGENTS, index + 4)
    order_id = _pick(ORDER_IDS, index + 3)
    return (
        f"Support agent {agent} took ownership of the escalated case within one hour of assignment and reviewed "
        f"the full ticket history tied to order {order_id}, including the missing handoffs between tier-one and "
        f"specialist queues. He identified that the case had been miscategorized at intake, which routed it to a "
        f"general backlog instead of the technical response team equipped to resolve the underlying issue. {agent} "
        f"called the customer directly, apologized for the delay, and provided a written action plan listing "
        f"investigation steps, expected update intervals, and a target resolution window of forty-eight hours. "
        f"He corrected the queue assignment, engaged the appropriate engineering liaison, and posted interim "
        f"progress notes after each internal checkpoint so the customer could follow along without submitting "
        f"additional follow-ups. To address the service impact, {agent} applied a billing adjustment for the "
        f"period affected by the slow response and enrolled the account in priority support for the next thirty "
        f"days. The core issue was resolved ahead of the committed deadline, and {agent} sent a closure summary "
        f"outlining root cause, corrective actions, and direct contact details if the problem resurfaced. A "
        f"supervisor quality review was completed to capture lessons learned and reduce miscategorization rates "
        f"in the intake workflow. The customer confirmed the fix held during a week of normal usage and closed "
        f"the ticket satisfied with the escalation handling."
    )


def _refund_complaint(index: int) -> str:
    agent_date = _pick(DATES, index + 5)
    amount = _pick(AMOUNTS, index + 2)
    order_id = _pick(ORDER_IDS, index + 4)
    return (
        f"A customer filed a refund request on {agent_date} after returning an item from order {order_id} more "
        f"than two weeks earlier without seeing the {amount} credit reflected on their statement. They provided "
        f"carrier tracking showing the return package was delivered to the warehouse eight business days ago, yet "
        f"the refund status in their account still displayed as pending with no estimated completion date. The "
        f"customer contacted support once before and was told processing typically takes five to seven business "
        f"days after warehouse receipt, but that window had already passed without an update or explanation. They "
        f"emphasized that the missing refund was blocking a planned purchase for their small business and creating "
        f"cash-flow pressure because the original charge remained on their corporate card. The customer uploaded "
        f"return confirmation emails, warehouse scan timestamps, and bank screenshots to demonstrate the charge was "
        f"still outstanding. They requested immediate refund processing, written confirmation of the transaction "
        f"reference number, and escalation if finance approval was causing the delay. The customer also asked "
        f"whether partial refunds or restocking deductions had been applied without notification and wanted a "
        f"full line-item breakdown of any adjustments before accepting the final credit amount."
    )


def _refund_solution(index: int) -> str:
    agent = _pick(AGENTS, index + 5)
    amount = _pick(AMOUNTS, index + 2)
    order_id = _pick(ORDER_IDS, index + 4)
    return (
        f"Support agent {agent} verified the return receipt in the warehouse management system for order {order_id} "
        f"and found the refund had been queued but stalled awaiting a secondary finance approval triggered by the "
        f"corporate card payment method. She obtained same-day approval from the refunds team, released the full "
        f"{amount} credit without restocking deductions, and updated the customer portal status from pending to "
        f"processed while on the phone with the customer. {agent} emailed a refund confirmation containing the "
        f"transaction reference, expected bank posting timeline of three to five business days, and a point-of-contact "
        f"for finance if the credit did not appear on schedule. She documented the approval bottleneck and opened "
        f"a process improvement task to bypass the redundant review step for returns with confirmed warehouse intake. "
        f"The customer received an automated notification when the refund message was submitted to the payment "
        f"processor and again when the processor acknowledged successful handoff to the card network. {agent} scheduled "
        f"a brief follow-up call two days later to confirm the credit appeared on the corporate statement and to "
        f"assist with placing the business purchase that had been delayed. She closed the case with a satisfaction "
        f"note after the customer confirmed funds were restored and expressed appreciation for the transparent "
        f"communication throughout the refund investigation."
    )


TOPIC_BUILDERS: list[tuple[str, Callable[[int], str], Callable[[int], str]]] = [
    ("billing", _billing_complaint, _billing_solution),
    ("delivery", _delivery_complaint, _delivery_solution),
    ("product", _product_complaint, _product_solution),
    ("subscription", _subscription_complaint, _subscription_solution),
    ("support", _support_complaint, _support_solution),
    ("refund", _refund_complaint, _refund_solution),
]


def build_complaint_records(count: int = 200) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for i in range(count):
        topic, complaint_builder, solution_builder = TOPIC_BUILDERS[i % len(TOPIC_BUILDERS)]
        records.append(
            {
                "complaint": complaint_builder(i),
                "solution": solution_builder(i),
                "topic": topic,
            }
        )
    return records


def write_complaint_files(output_dir: str | Path, count: int = 200, force: bool = True) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not force and any(output_dir.glob("*.json")):
        return output_dir

    records = build_complaint_records(count)
    for idx, record in enumerate(records):
        file_path = output_dir / f"complaint_{idx + 1:03d}.json"
        with file_path.open("w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2)

    return output_dir
