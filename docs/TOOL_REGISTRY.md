# Tool Registry

> Skeleton — to be completed alongside M4 and M7.

Each tool must declare: `name`, `description`, `input_schema`, `output_schema`,
`required_groups`, `requires_approval`, `side_effects`, `rate_limit`.

## Safe read tools (M4, no approval required)

| Tool | Side effects | Notes |
|---|---|---|
| `search_records` | read | Domain search across any permitted model |
| `read_record` | read | Fetch a single record by id |
| `list_views` | read | List available views for a model |
| `semantic_search` | read | pgvector similarity search (M5) |

## Write tools (M4+, approval required)

| Tool | Side effects | Notes |
|---|---|---|
| *(none yet)* | — | Defined per vertical in M7 |
