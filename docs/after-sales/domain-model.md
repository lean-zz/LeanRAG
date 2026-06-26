# AfterSales Copilot Domain Model

## Personas

- Customer: owns an X100 device and needs product, warranty, return, or repair help.
- Support Agent: uses the assistant while replying to customers in chat, email, or phone support.
- Support Engineer: investigates fault codes, repair decisions, and field escalation cases.
- Support Operations Manager: reviews answer quality, missing knowledge, intent routing, and trace data.

## Core Terms

- Product Model: a serviceable model such as X100.
- Serial Number: a unique product identifier such as SN-X100-2026-0001.
- Ticket: an after-sales case such as T-10001.
- Warranty: coverage status, start and end dates, exclusions, and required proof.
- Return Window: the period when a customer may request return or exchange.
- Fault Code: a product error code such as E01, E17, E37, or N04.
- Troubleshooting SOP: a safe diagnostic procedure for support agents and engineers.
- Service Center: an authorized location for inspection, repair, or replacement.
- Escalation: handoff to senior support, safety team, legal, payment, or field service.

## Question Categories

- Product usage: setup, cleaning, charging, accessories, compatibility.
- Troubleshooting: symptoms, fault codes, restart loops, abnormal display, network failures.
- Warranty and return policy: coverage, exclusions, proof, deadlines, inspection.
- Ticket status: case owner, current stage, next action, expected response time.
- Service-center lookup: supported city, appointment rules, repair lead time.
- Product lookup: map serial number to model, batch, purchase date, and warranty profile.
- Clarification: ask for missing serial number, ticket ID, city, product model, or fault code.
- Escalation: smoke, burning smell, injury, payment dispute, privacy issue, or repeated repair failure.

## Answer Categories

- Knowledge-only: answer using FAQ, manual, policy, or SOP documents.
- Tool-only: answer using structured business data such as ticket or warranty status.
- Mixed: combine policy documents with tool results.
- Clarification required: ask for the missing field before giving operational guidance.
- Escalation required: stop risky instructions and recommend human handling.

## Answer Contract

Most answers should include:

- Conclusion: direct answer.
- Basis: document, policy, SOP, or tool result used.
- Steps: actionable customer or support-agent steps.
- Need To Confirm: missing details, if any.
- Escalation: whether human escalation is recommended and why.

Troubleshooting answers should include:

- Likely Causes.
- Customer Checks.
- Support-Agent Checks.
- Escalation Conditions.
- Basis.

## Escalation Rules

Escalate immediately when the customer reports smoke, burning smell, electric shock, injury, water ingress with power on, swelling battery, payment dispute, privacy exposure, repeated repair failure, legal threat, or a VIP enterprise outage.

For safety-sensitive cases, do not instruct the customer to keep powering the device on. Ask them to disconnect power, stop use, preserve evidence, and create or update a ticket for specialist handling.
