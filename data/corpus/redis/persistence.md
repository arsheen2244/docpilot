# Redis Persistence

## RDB snapshots
RDB writes point-in-time snapshots of the dataset at configured intervals. Files are compact and restarts are fast, but writes since the last snapshot are lost if the server crashes.

## Append-only file
AOF logs every write operation. The appendfsync setting controls durability: always syncs on every write and is the safest but slowest, everysec syncs once per second and risks about one second of data, and no leaves syncing to the operating system. The log is periodically rewritten to keep it small.

## Combining both
Running both RDB and AOF is common. On restart Redis prefers the AOF because it is usually the more complete record.
