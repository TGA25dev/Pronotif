import sentry_sdk
from sentry_sdk.scrubber import EventScrubber
from sentry_sdk import logger as sentry_logger
from loguru import logger

version = "v0.9"
ignore_errors = [KeyboardInterrupt]

def before_send(event, hint):
    # Scrub request data
    if "request" in event:
        request = event["request"]

        #Remove cookies and request bodies
        request.pop("cookies", None)
        request.pop("data", None)

        #Remove headers
        if "headers" in request:
            request.pop("headers", None)

        #Scrub query strings(remove params)
        if "url" in request:
            from urllib.parse import urlparse
            parsed = urlparse(request["url"])
            request["url"] = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    if "user" in event:
        event["user"].clear()

    return event

# Initialize with base configuration
sentry_sdk.init("https://8c5e5e92f5e18135e5c89280db44a056@o4508253449224192.ingest.de.sentry.io/4508253458726992", 
                enable_tracing=True,
                traces_sample_rate=0.2,
                environment="production",
                release=version,
                server_name="Server",
                ignore_errors=ignore_errors,
                send_default_pii=False,
                event_scrubber=EventScrubber(),
                before_send=before_send
)


def get_logger_enabled_sentry():
    sentry_sdk.init("https://8c5e5e92f5e18135e5c89280db44a056@o4508253449224192.ingest.de.sentry.io/4508253458726992", 
                    enable_tracing=True,
                    traces_sample_rate=0.2,
                    environment="production",
                    release=version,
                    server_name="Server",
                    ignore_errors=ignore_errors,
                    send_default_pii=False,
                    event_scrubber=EventScrubber(),
                    before_send=before_send,
                    _experiments={
                        "enable_logs": True,
                    }
    )
    return sentry_sdk, sentry_logger, logger