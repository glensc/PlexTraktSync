from time import sleep
from plexapi.server import PlexServer

from plex_trakt_sync.logging import logging

PLAYING = "playing"

EVENTS = {
    "account": "AccountUpdateNotification",
    "activity": "ActivityNotification",
    "backgroundProcessingQueue": "BackgroundProcessingQueueEventNotification",
    "playing": "PlaySessionStateNotification",
    "preference": "Setting",
    "progress": "ProgressNotification",
    "reachability": "ReachabilityNotification",
    "status": "StatusNotification",
    "timeline": "TimelineEntry",
}


class EventFactory:
    def get_events(self, message):
        if message["size"] != 1:
            raise ValueError("Unexpected size: %r" % message)

        message_type = message['type']
        if message_type not in EVENTS:
            return
        class_name = EVENTS[message_type]
        if class_name not in message:
            return
        for data in message[class_name]:
            event = self.create(cls=class_name, **data)
            yield event

    def create(self, cls, **kwargs):
        # https://stackoverflow.com/a/2827726/2314626
        return type(cls, (object,), kwargs)


class WebSocketListener:
    def __init__(self, plex: PlexServer, interval=1):
        self.plex = plex
        self.interval = interval
        self.event_handlers = {}
        self.logger = logging.getLogger("PlexTraktSync.WebSocketListener")

    def on(self, event_name, handler):
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []

        self.event_handlers[event_name].append(handler)

    def listen(self):
        def handler(data):
            self.logger.debug(data)
            event_type = data['type']
            if event_type not in self.event_handlers:
                return

            for handler in self.event_handlers[event_type]:
                handler(data)

        while True:
            notifier = self.plex.startAlertListener(callback=handler)
            while notifier.is_alive():
                sleep(self.interval)

            self.logger.debug(f"Listener finished. Restarting in {self.interval}")
            sleep(self.interval)
