# PostgreSQL Indexes

## B-tree
B-tree is the default index type and supports equality and range queries as well as sorting. It suits most columns.

## Specialised index types
GIN indexes handle values that contain many elements, such as arrays, jsonb documents and full-text search vectors. GiST supports geometric data and nearest-neighbour searches. BRIN stores summaries of block ranges and is very small, which works well for huge tables whose values correlate with physical order, such as timestamps in an append-only table. Hash indexes only support equality.

## Partial and covering indexes
A partial index covers only rows matching a WHERE condition, reducing size. A covering index uses the INCLUDE clause to add extra columns so that queries can be answered with an index-only scan without visiting the table.
