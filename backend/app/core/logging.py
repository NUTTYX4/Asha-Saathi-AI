"""Logging setup. Never log API keys, audio, transcript text, or a worker's location."""

import logging


class RedactQueryString(logging.Filter):
    """Keep the path but drop the query string from uvicorn access-log lines.

    A query string can hold a worker's GPS position (/api/v2/households/nearby?lat=..&lon=..)
    or search text, and container logs must not retain either. uvicorn logs access lines as
    '%s - "%s %s HTTP/%s" %d' with the path (including its query string) as the third argument.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str) and "?" in args[2]:
            record.args = (*args[:2], args[2].split("?", 1)[0] + "?[redacted]", *args[3:])
        return True


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactQueryString) for f in access.filters):
        access.addFilter(RedactQueryString())
