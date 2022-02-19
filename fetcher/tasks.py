import os
import datetime as dt
import requests
import feedparser
from typing import Dict
import logging
import time
import hashlib
from sqlalchemy.exc import IntegrityError

from fetcher import path_to_log_dir
from fetcher.celery import app
from fetcher.database import Session, engine
import fetcher.database.models as models

logger = logging.getLogger(__name__)  # get_task_logger(__name__)
logFormatter = logging.Formatter("[%(levelname)s %(threadName)s] - %(asctime)s - %(name)s - : %(message)s")
fileHandler = logging.FileHandler(os.path.join(path_to_log_dir, "tasks-{}.log".format(time.strftime("%Y%m%d-%H%M%S"))))
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)


RSS_FETCH_TIMEOUT_SECS = 30


@app.task(serializer='json', bind=True)
def feed_worker(self, feed: Dict):
    """
    Fetch a feed, parse out stories, store them
    :param self:
    :param feed:
    """
    try:
        logger.debug("Working on feed {}".format(feed['id']))
        fetched_at = dt.datetime.now()
        response = requests.get(feed['url'], timeout=RSS_FETCH_TIMEOUT_SECS)
        if response.status_code == 200:
            new_hash = hashlib.md5(response.content).hexdigest()
            if new_hash != feed['last_fetch_hash']:
                # try to reduce overall connection churn but holding one connection per task
                with engine.connect() as connection:  # will call close automatically
                    # first mark the success
                    with Session(bind=connection) as session:
                        f = session.query(models.Feed).get(feed['id'])
                        f.last_fetch_success = fetched_at
                        f.last_fetch_hash = new_hash
                        session.commit()
                    # now add all the stories
                    parsed_feed = feedparser.parse(response.content)
                    for entry in parsed_feed.entries:
                        s = models.Story.from_rss_entry(feed['id'], fetched_at, entry)
                        # need to commit one by one so duplicate URL keys don't stop a larger insert from happening
                        # those are *expected* errors, so we can ignore them
                        with Session(bind=connection) as session:
                            try:
                                session.add(s)
                                session.commit()
                            except IntegrityError as _:
                                logger.debug("duplicate URL: {}".format(s.url))
                logger.info("  Feed {} - {} entries".format(feed['id'], len(parsed_feed.entries)))
            else:
                logger.info("  Feed {} - skipping, same hash".format(feed['id']))
        else:
            logger.info("  Feed {} - skipping, bad response {}".format(feed['id'], response.status_code))
    except Exception as exc:
        # maybe we server didn't respond? ignore as normal operation perhaps?
        logger.error(" Feed {}: error: {}".format(feed['id'], exc))
