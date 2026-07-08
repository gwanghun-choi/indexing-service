import logging


class SensitiveDataFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.sensitive_fields = {"password", "token", "secret", "api_key"}

    def filter(self, record):
        if hasattr(record, "msg") and isinstance(record.msg, dict):
            record.msg = self._filter_sensitive_data(record.msg)
        return True

    def _filter_sensitive_data(self, data):
        if isinstance(data, dict):
            return {
                k: "[FILTERED]"
                if k.lower() in self.sensitive_fields
                else self._filter_sensitive_data(v)
                for k, v in data.items()
            }
        return data
