# After-Sales Mock Tool Contracts

The V2 mock tools are deterministic demo adapters exposed through `POST /tools/{tool_name}/invoke`. They return MCP-style payloads with `tool`, `isError`, `content`, and `result`.

## get_ticket_status(ticket_id)

Purpose: return current after-sales ticket state and next action.

Required parameters:

- `ticket_id`: ticket ID such as `T-10001`.

Demo success IDs:

- `T-10001`: awaiting customer confirmation after remote troubleshooting.
- `T-10002`: waiting for service-center inspection and paid-repair quotation.

Not found behavior:

- `isError: true`
- Result text includes the unknown ticket ID and asks the caller to verify it.

## get_warranty_status(serial_number)

Purpose: return warranty status, coverage dates, exclusions, and linked product metadata.

Required parameters:

- `serial_number`: serial number such as `SN-X100-2026-0001`.

Demo success IDs:

- `SN-X100-2026-0001`: `in_warranty`, coverage ends `2028-05-20`.
- `SN-X100-2024-0099`: `expired`, coverage ended `2026-03-12`.

Not found behavior:

- `isError: true`
- Result text includes the unknown serial number and asks for confirmation.

## find_service_center(city, product_model)

Purpose: return demo authorized service-center information for X100.

Required parameters:

- `city`: `Shanghai`, `Beijing`, `Shenzhen`, or `Chengdu`.
- `product_model`: `X100`.

Demo success behavior:

- Returns center name, address, appointment requirement, inspection lead time, and repair lead time.

Unsupported city behavior:

- `isError: true`
- Result text recommends mail-in repair for unsupported cities.

## get_product_by_serial(serial_number)

Purpose: return product model, batch, purchase date, and registered customer metadata.

Required parameters:

- `serial_number`: serial number such as `SN-X100-2024-0099`.

Demo success IDs:

- `SN-X100-2026-0001`
- `SN-X100-2024-0099`

Not found behavior:

- `isError: true`
- Result text asks the support agent to confirm the serial label or invoice.

## Replacement Guidance

When replacing mocks with real adapters, keep the tool names stable and preserve error semantics. Real adapters should sanitize parameters in trace data, avoid returning sensitive raw customer data, and include an auditable status for each tool call.
