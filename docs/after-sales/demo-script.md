# AfterSales Copilot Demo Script

## Demo Questions

1. FAQ: "What should a customer do before using X100 for the first time?"
   Expected route: knowledge-only. Expected basis: X100 FAQ.

2. FAQ: "Can X100 be cleaned with alcohol wipes?"
   Expected route: knowledge-only. Expected basis: X100 FAQ.

3. FAQ: "Which accessories are compatible with X100?"
   Expected route: knowledge-only. Expected basis: X100 FAQ.

4. Warranty: "Is accidental water damage covered by the X100 warranty?"
   Expected route: knowledge-only. Expected basis: warranty policy.

5. Warranty: "SN-X100-2026-0001 is noisy after startup. Is it still under warranty?"
   Expected route: mixed. Expected basis: warranty tool plus warranty policy.

6. Troubleshooting: "X100 displays E37. What should the customer check first?"
   Expected route: knowledge-only. Expected basis: troubleshooting SOP.

7. Troubleshooting: "X100 cannot start after charging overnight."
   Expected route: knowledge-only. Expected basis: troubleshooting SOP for E01 and cannot-start flow.

8. Ticket: "What is the status of ticket T-10001?"
   Expected route: tool-only. Expected basis: get_ticket_status.

9. Ticket: "Ticket T-10002 has not moved. What should the support agent do next?"
   Expected route: tool-only. Expected basis: get_ticket_status.

10. Service center: "Where can I repair X100 in Shanghai?"
    Expected route: tool-only. Expected basis: find_service_center.

11. Clarification: "My device is broken. Can I return it?"
    Expected route: clarification. Missing fields: product model, purchase date, serial number, issue symptom.

12. Escalation: "The machine is smoking. Can I keep powering it on to test?"
    Expected route: escalation. Expected answer: stop use, disconnect power, preserve evidence, escalate.

## Version Smoke Tests

V0 proves the domain, data, and routes are concrete. V1 proves FAQ, warranty, and troubleshooting questions render support-style answers. V2 proves ticket, warranty, product, and service-center tool calls. V3 proves operations staff can diagnose a poor answer from trace data. V4 proves citation, escalation, audit, and regression controls.

## Demo IDs

- Product model: X100.
- Serial numbers: SN-X100-2026-0001, SN-X100-2024-0099.
- Tickets: T-10001, T-10002.
- Cities: Shanghai, Beijing, Shenzhen, Chengdu.
