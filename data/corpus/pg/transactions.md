# PostgreSQL Transactions and Isolation

## Isolation levels
The default isolation level is Read Committed, where each statement sees data committed before that statement began. Repeatable Read gives every statement in the transaction the same snapshot. Serializable adds predicate tracking so that outcomes match some serial order, and applications must be ready to retry on serialization failures.

## Read Uncommitted
PostgreSQL accepts Read Uncommitted but treats it exactly like Read Committed, so dirty reads never occur.

## Locking
Row-level locks can be taken explicitly with SELECT FOR UPDATE. Deadlocks are detected automatically and one of the transactions is aborted.
