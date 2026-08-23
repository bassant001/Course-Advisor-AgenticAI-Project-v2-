import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):

    # bey7awel el logs le JSON format
    # 3ashan teb2a sahla lel monitoring w analysis
    def format(self, record: logging.LogRecord) -> str:
        # benegama3 el important information beta3et kol request
        log_record = {

            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname, # level zay INFO / WARNING / ERROR
            "event": getattr(record, "event", record.getMessage()),# event name beta3 el operation
        }

        if hasattr(record, "method"): # http method zay get aw post
            log_record["method"] = record.method

        if hasattr(record, "path"): # endpoint zay / advise
            log_record["path"] = record.path

        if hasattr(record, "status_code"): # http response status zay 200 aw 500
            log_record["status_code"] = record.status_code

        if hasattr(record, "duration_ms"): # w2t el request estaghrab feh bel milliseconds
            log_record["duration_ms"] = record.duration_ms

        return json.dumps(log_record) # ben7awel el dictionary le JSON string


def setup_logging():

    logger = logging.getLogger("course_advisor") # Bengeeb logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    # nemsa7 ay handlers adeema 3ashan man3mlsh duplicate logs
    logger.handlers.clear()
    # nerbat el handler bel logger
    logger.addHandler(handler)

    logger.propagate = False

    return logger