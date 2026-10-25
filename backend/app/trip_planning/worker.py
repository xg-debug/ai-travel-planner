"""Run with: python -m app.trip_planning.worker"""

import logging
import threading
import time

from app.trip_planning.jobs import trip_planning_job_service

logger = logging.getLogger(__name__)


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Planning worker ready")
    while True:
        try:
            claim = trip_planning_job_service.claim()
            if claim is None:
                time.sleep(1)
                continue
            job_id, attempt = claim
            stopped = threading.Event()

            def keep_lease() -> None:
                while not stopped.wait(30):
                    try:
                        if not trip_planning_job_service.heartbeat(job_id, attempt):
                            return
                    except Exception:
                        logger.exception("Could not renew planning lease job_id=%s", job_id)

            heartbeat = threading.Thread(target=keep_lease, daemon=True)
            heartbeat.start()
            try:
                trip_planning_job_service.run_claimed(job_id, attempt)
            finally:
                stopped.set()
                heartbeat.join(timeout=1)
        except Exception:
            logger.exception("Planning worker loop failed")
            time.sleep(2)


if __name__ == "__main__":
    run_forever()
