# After-Sales Tool Parameter Extraction

Extract only parameters needed by after-sales support tools. Return strict JSON.

Supported tools:

- get_ticket_status(ticket_id)
- get_warranty_status(serial_number)
- find_service_center(city, product_model)
- get_product_by_serial(serial_number)

Rules:

- Ticket IDs look like T-10001.
- Serial numbers look like SN-X100-2026-0001.
- Product models look like X100.
- Cities include Shanghai, Beijing, Shenzhen, and Chengdu in the demo data.
- If a required parameter is missing, return null for that field and include it in missingFields.

Examples:

Question: What is the status of ticket T-10001?
JSON: {"tool":"get_ticket_status","parameters":{"ticket_id":"T-10001"},"missingFields":[]}

Question: Is SN-X100-2026-0001 still under warranty?
JSON: {"tool":"get_warranty_status","parameters":{"serial_number":"SN-X100-2026-0001"},"missingFields":[]}

Question: Where can I repair product X100 in Shanghai?
JSON: {"tool":"find_service_center","parameters":{"city":"Shanghai","product_model":"X100"},"missingFields":[]}

Question: What product is SN-X100-2024-0099?
JSON: {"tool":"get_product_by_serial","parameters":{"serial_number":"SN-X100-2024-0099"},"missingFields":[]}

Question: SN-X100-2024-0099 is already out of warranty. Can it still be repaired?
JSON: {"tool":"get_warranty_status","parameters":{"serial_number":"SN-X100-2024-0099"},"missingFields":[]}

Question: My X100 needs repair in Chengdu.
JSON: {"tool":"find_service_center","parameters":{"city":"Chengdu","product_model":"X100"},"missingFields":[]}

Question: Where is my case now?
JSON: {"tool":null,"parameters":{},"missingFields":["ticket_id"]}
