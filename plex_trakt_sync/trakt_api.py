from json import JSONDecodeError
from typing import Union
import trakt

from plex_trakt_sync import pytrakt_extensions
from plex_trakt_sync.path import pytrakt_file
from plex_trakt_sync.plex_api import PlexLibraryItem

trakt.core.CONFIG_PATH = pytrakt_file
import trakt.users
import trakt.sync
import trakt.movies
from trakt.movies import Movie
from trakt.tv import TVShow, TVSeason, TVEpisode
from trakt.errors import OAuthException, ForbiddenException
from trakt.sync import Scrobbler

from plex_trakt_sync.logging import logger
from plex_trakt_sync.decorators import memoize, nocache, rate_limit
from plex_trakt_sync.config import CONFIG

TRAKT_POST_DELAY = 1.1


class ScrobblerProxy:
    """
    Proxy to Scrobbler that handles requsts cache and rate limiting
    """

    def __init__(self, scrobbler: Scrobbler):
        self.scrobbler = scrobbler

    @nocache
    @rate_limit(delay=TRAKT_POST_DELAY)
    def update(self, progress: float):
        self.scrobbler.update(progress)

    @nocache
    @rate_limit(delay=TRAKT_POST_DELAY)
    def pause(self):
        self.scrobbler.pause()

    @nocache
    @rate_limit(delay=TRAKT_POST_DELAY)
    def stop(self):
        self.scrobbler.stop()


class TraktApi:
    """
    Trakt API class abstracting common data access and dealing with requests cache.
    """

    @property
    @memoize
    @nocache
    @rate_limit()
    def me(self):
        try:
            return trakt.users.User('me')
        except (OAuthException, ForbiddenException) as e:
            logger.fatal("Trakt authentication error: {}".format(str(e)))
            raise e

    @property
    @memoize
    @nocache
    @rate_limit()
    def liked_lists(self):
        if not CONFIG['sync']['liked_lists']:
            return []
        return pytrakt_extensions.get_liked_lists()

    @property
    @memoize
    @nocache
    @rate_limit()
    def watched_movies(self):
        return set(
            map(lambda m: m.trakt, self.me.watched_movies)
        )

    @property
    @memoize
    @nocache
    @rate_limit()
    def movie_collection(self):
        return self.me.movie_collection

    @property
    @memoize
    @nocache
    @rate_limit()
    def show_collection(self):
        return self.me.show_collection

    @nocache
    @rate_limit(delay=TRAKT_POST_DELAY)
    def remove_from_library(self, media: Union[Movie, TVShow, TVSeason, TVEpisode]):
        if not isinstance(media, (Movie, TVShow, TVSeason, TVEpisode)):
            raise ValueError("Must be valid media type")
        media.remove_from_library()

    @property
    @memoize
    def movie_collection_set(self):
        return set(
            map(lambda m: m.trakt, self.movie_collection)
        )

    @property
    @memoize
    @nocache
    @rate_limit()
    def watched_shows(self):
        return pytrakt_extensions.allwatched()

    @property
    @memoize
    @nocache
    @rate_limit()
    def watchlist_movies(self):
        if not CONFIG['sync']['watchlist']:
            return []

        return list(
            map(lambda m: m.trakt, self.me.watchlist_movies)
        )

    @property
    @memoize
    @nocache
    @rate_limit()
    def movie_ratings(self):
        return self.me.get_ratings(media_type='movies')

    @property
    @memoize
    def ratings(self):
        ratings = {}
        for r in self.movie_ratings:
            ratings[r['movie']['ids']['slug']] = r['rating']

        return ratings

    def rating(self, m):
        if m.slug in self.ratings:
            return int(self.ratings[m.slug])

        return None

    @nocache
    @rate_limit(delay=TRAKT_POST_DELAY)
    def rate(self, m, rating):
        m.rate(rating)

    def scrobbler(self, media: Union[Movie, TVEpisode]) -> ScrobblerProxy:
        scrobbler = media.scrobble(0, None, None)
        return ScrobblerProxy(scrobbler)

    @nocache
    @rate_limit(delay=TRAKT_POST_DELAY)
    def mark_watched(self, m, time):
        m.mark_as_seen(time)

    @nocache
    @rate_limit(delay=TRAKT_POST_DELAY)
    def add_to_collection(self, m, pm: PlexLibraryItem):
        # support is missing, compose custom json ourselves
        # https://github.com/moogar0880/PyTrakt/issues/143
        if m.media_type == "movies":
            json = {
                m.media_type: [dict(
                    title=m.title,
                    year=m.year,
                    **m.ids,
                    **pm.to_json(),
                )],
            }
            return trakt.sync.add_to_collection(json)
        else:
            return m.add_to_library()

    @memoize
    @nocache
    @rate_limit()
    def collected(self, tm: TVShow):
        return pytrakt_extensions.collected(tm.trakt)

    @memoize
    @nocache
    @rate_limit()
    def lookup(self, tm: TVShow):
        """
        This lookup-table is accessible via lookup[season][episode]
        """
        return pytrakt_extensions.lookup_table(tm)

    @memoize
    @rate_limit()
    def find_movie(self, media: PlexLibraryItem):
        try:
            search = trakt.sync.search_by_id(media.id, id_type=media.provider, media_type=media.media_type)
        except JSONDecodeError as e:
            raise ValueError(f"Unable parse search result for {media.provider}/{media.id}: {e.doc!r}") from e
        except ValueError as e:
            # Search_type must be one of ('trakt', ..., 'imdb', 'tmdb', 'tvdb')
            raise ValueError(f"Invalid id_type: {media.provider}") from e
        # look for the first wanted type in the results
        for m in search:
            if m.media_type == media.type:
                return m

        return None
