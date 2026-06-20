# cache

Per-account TTL cache for rarely-changing reference data (grades list,
teachers, academic periods, X1 model map). `ReferenceCache` stores any
value under a string key with a configurable TTL (default 300 s); expired
entries are evicted on the next `get()`. One instance lives on the `Client`
and is shared across all method calls for that account.
