---
name: Bug report
about: Report unexpected behaviour in an endpoint, a query, or the data layer
title: "[BUG] "
labels: bug
assignees: ''
---

### What happened?
<!-- One-sentence summary. -->

### What did you expect to happen?

### Steps to reproduce
1. ...
2. ...
3. ...

### Minimal request (if applicable)
```bash
curl -X POST http://localhost:8000/places/nearby \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Actual response

```json
{...}
```

### Environment

- Python version: <!-- e.g. 3.13.5 -->
- OS: <!-- e.g. Windows 11, macOS 14, Ubuntu 22.04 -->
- Install path: <!-- pip / docker -->
- Commit: <!-- git rev-parse HEAD -->

### Anything else
<!-- Logs, screenshots, hypotheses. -->
