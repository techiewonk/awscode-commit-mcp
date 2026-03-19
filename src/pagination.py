"""nextToken / maxResults helpers for list and diff APIs."""

# Pagination is passed through to boto3; this module can hold shared defaults.
DEFAULT_MAX_RESULTS = 100
MAX_RESULTS_CAP = 1000
