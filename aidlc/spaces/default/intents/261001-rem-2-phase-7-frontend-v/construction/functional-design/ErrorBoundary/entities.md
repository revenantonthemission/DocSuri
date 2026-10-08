# Entities — ErrorBoundary

**Unit:** ErrorBoundary
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Entity Definitions

### ErrorInfo
**Owner:** ErrorBoundary
**Identifier:** `errorId` (string, UUID v4)

| Attribute | Type | Description |
|-----------|------|-------------|
| errorId | string | UUID v4 |
| error | Error | The caught error object |
| errorInfo | object | React error info (componentStack) |
| timestamp | number | Unix timestamp (ms) |
| componentName | string | Name of component that threw |

**References:** None (owned by ErrorBoundary)

---

### ErrorBoundaryState
**Owner:** ErrorBoundary
**Identifier:** N/A (component state)

| Attribute | Type | Description |
|-----------|------|-------------|
| hasError | boolean | Whether an error was caught |
| error | Error | The caught error object |
| errorInfo | object | React error info (componentStack) |