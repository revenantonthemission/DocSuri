# Reliability Design — IdempotencyService

## NFR4.1: Persistence Across Reloads
**Design**: localStorage (not sessionStorage) → survives browser restart

## NFR4.2: Corruption Resilience
**Design**: try/catch on parse; corrupted → delete → regenerate
```ts
function getKey(paperId, taskType) {
  try {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : null;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}
```

## NFR4.3: Quota Exceeded Handling
**Design**: Catch `QuotaExceededError` → purge oldest → retry → fallback to Map
```ts
try { localStorage.setItem(key, value); }
catch (e) {
  if (e.name === 'QuotaExceededError') {
    purgeOldestKeys();
    try { localStorage.setItem(key, value); }
    catch { memoryFallback.set(key, value); }
  }
}
```

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR4.1 | localStorage persistence |
| NFR4.2 | try/catch + delete + regenerate |
| NFR4.3 | QuotaExceededError → purge → Map fallback |