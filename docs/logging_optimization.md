# Logging Optimization

## Overview

Optimized logging configuration to reduce verbose output from third-party libraries and Qt internals while maintaining application-level debug visibility.

## Changes

### 1. Third-Party Library Suppression

Reduced logging level for verbose HTTP connection libraries:

```python
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("urllib3.util.retry").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
```

**Impact**: Eliminates detailed connection pool messages like:
- `Starting new HTTPS connection (1): u.y.qq.com:443`
- `https://u.y.qq.com:443 "POST /cgi-bin/musicu.fcg HTTP/1.1" 200 191`

Only connection warnings and errors are now shown.

### 2. Qt Message Filtering

Installed custom Qt message handler to filter verbose Qt internals:

```python
def qt_message_handler(mode, context, message):
    """Filter out verbose Qt debug messages."""
    suppressed_messages = [
        "Using Qt multimedia with FFmpeg",
        "Parent future has",
        "AtSpiAdaptor::applicationInterface",
    ]
    # ... filtering logic
```

**Impact**: Eliminates Qt debug spam:
- `qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version...`
- `qt.core.qfuture.continuations: Parent future has 2 result(s)...`
- `qt.accessibility.atspi: AtSpiAdaptor::applicationInterface...`

## Benefits

- **Cleaner logs**: Focus on application-level messages
- **Better performance**: Reduced I/O from verbose logging
- **Easier debugging**: Signal-to-noise ratio improved

## Configuration

Logging levels can be adjusted in `main.py`:

- **DEBUG**: Show all application messages, filtered third-party
- **INFO**: Show informational messages and above
- **WARNING**: Show warnings and errors only

## Future Improvements

Consider implementing:
- Log rotation for long-running sessions
- Configurable log levels via settings
- Structured logging (JSON) for log analysis tools
