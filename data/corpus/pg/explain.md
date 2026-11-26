# Reading Query Plans in PostgreSQL

## EXPLAIN
EXPLAIN shows the plan the planner chose along with estimated costs and row counts, without running the query. EXPLAIN ANALYZE actually executes the query and reports real timings and row counts, so wrap data-modifying statements in a transaction you roll back.

## Scan types
A sequential scan reads the whole table. An index scan follows the index to individual rows. A bitmap scan collects matching locations from the index first and then reads the pages in order, which suits queries returning a moderate number of rows.

## Bad estimates
When estimated and actual row counts differ greatly, the planner statistics are likely stale. Running ANALYZE refreshes them. Adding the BUFFERS option shows how many pages came from cache versus disk.
