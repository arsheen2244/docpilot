# Redis Eviction Policies

## maxmemory
When memory use reaches the maxmemory limit, Redis applies the configured maxmemory-policy. With the default noeviction policy, writes that need more memory return an error while reads continue.

## Policies
allkeys-lru evicts the least recently used keys from all keys, and allkeys-lfu evicts the least frequently used. volatile-lru and volatile-lfu consider only keys that have an expiry set. volatile-ttl evicts keys closest to expiring. The random policies pick keys arbitrarily.

## Choosing
Use allkeys-lru for a general cache. Use a volatile policy when some keys must never be evicted and only expiring keys are cache entries.
