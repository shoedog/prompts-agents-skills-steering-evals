# http_client.get_json

`get_json(url, retries=3)` fetches and decodes a JSON response, with retries.

Contract:
- Make up to `retries` attempts on TRANSIENT failures only (connection
  errors, timeouts, HTTP 5xx).
- A NON-transient failure (HTTP 4xx, or a JSON decode error) is permanent
  and MUST propagate to the caller so it is distinguishable from a valid
  empty response.
- On success return the decoded JSON.
