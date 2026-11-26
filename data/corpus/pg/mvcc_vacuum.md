# PostgreSQL MVCC and Vacuum

## Multiversion concurrency control
PostgreSQL uses MVCC so readers do not block writers. An update does not overwrite a row; it writes a new row version and marks the old one as no longer visible to newer transactions.

## Why vacuum is needed
Old row versions that no transaction can see become dead tuples and take up space. VACUUM marks that space reusable, and autovacuum runs it in the background based on thresholds. VACUUM FULL rewrites the whole table to return space to the operating system, but it takes an exclusive lock for the duration.

## Transaction ID wraparound
Transaction IDs are 32 bits, so vacuum must periodically freeze old rows. If freezing falls too far behind, PostgreSQL will stop accepting writes to protect data.
