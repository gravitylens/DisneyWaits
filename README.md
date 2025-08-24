# DisneyWaits

Service that polls the [queue-times](https://queue-times.com) API for
attraction wait times at Disney parks. Only parks listed under "Walt Disney
Attractions" are tracked and ride data is flattened across park areas.  It
keeps a five day running average and standard deviation for each ride and
flags rides with a current wait more than one standard deviation below their
average.

## Running locally

```bash
python -m pip install -r requirements.txt
uvicorn disneywaits.service:app --reload
```

The service exposes:

- `GET /parks` – list of known parks
- `GET /wait_times?park_id={id}` – current wait times and statistics for all
  rides, optionally filtered to a single park
- `GET /parks/{park_id}/wait_times` – legacy endpoint equivalent to the above

## Docker

```bash
docker build -t disneywaits .
docker run -p 8000:8000 disneywaits
```

The service polls the API every five minutes while running.
