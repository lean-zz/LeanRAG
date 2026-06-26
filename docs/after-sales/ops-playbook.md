# AfterSales Copilot Operations Playbook

## Daily Review

Support operations should review recent answer traces, low-confidence answers, no-answer cases, tool-call failures, and user feedback. Each poor answer should be mapped to one remediation path: add a document, edit chunks, adjust intent examples, add term mappings, fix tool output, or update prompt rules.

## Fix Missing Documents

When the answer says there is insufficient information and the trace shows no relevant retrieval, add or update the source document in the after-sales knowledge base. Prefer product FAQ, warranty policy, return policy, troubleshooting SOP, or service-center policy. Re-ingest the document and rerun the failed sample question.

## Fix Bad Chunks

When retrieval finds the right document but the answer misses a rule, inspect the matched chunks. If a chunk mixes unrelated policy clauses or splits a required procedure, revise headings and paragraph boundaries in the source document, then re-ingest. Keep fault-code headings such as E37 and N04 visible.

## Fix Intent Classification

When trace shows the question routed to the wrong intent, edit the intent node description and examples. Add realistic customer phrases, ticket IDs, serial number patterns, and city examples. Keep the tree shallow unless repeated traces show a stable subcategory.

## Fix Term Mappings

When customers use colloquial language that retrieval misses, add a query-term mapping. Examples: "cannot turn on" to "cannot start", "black screen" to "display abnormality", "broken" to "fault", and "repair one" to "repair service".

## Fix Tool Output

When the selected tool is right but the answer is wrong, inspect the tool-call trace. Confirm parameters, sanitized inputs, response status, duration, and returned fields. Fix mock data or the adapter contract before changing prompts.

## Trace Reading Checklist

- Rewrite: did the rewritten question preserve ticket ID, serial number, fault code, and city?
- Intent: did the top intent match the expected route?
- Retrieval: did the selected chunks include the policy or SOP clause?
- Tool call: were required parameters extracted and passed?
- Prompt: did the prompt include document basis and tool basis?
- Generation: did the final answer overclaim, omit escalation, or miss required sections?
