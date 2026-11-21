# CAPTCHA Feedback

A small Python service for collecting manually submitted CAPTCHA category feedback.

It is for testing how well a program identifies the *type* of challenge, such as a
text prompt or an image grid. It does not solve challenges, submit answers, or approve
verification checks. It also does not collect challenge screenshots or answer text.

## What gets saved

Each report contains:

- The category selected by the person submitting the report.
- The category shown by the detector, if there was one.
- The client version and the time of submission.

The database does not store IP addresses, screenshots, browser cookies, tokens, or
account names. The server uses the connecting IP address temporarily for a basic
submission limit. Your hosting provider may also keep its own request logs, so check
its privacy settings before inviting other people to use a hosted copy.

## Install on Termux

```sh
pkg update
pkg install python

git clone https://github.com/rabbitgubbyking-creator/Cupcha-slover-.git
cd Cupcha-slover-
python -m pip install -r requirements.txt
```

Start the server on the phone:

```sh
uvicorn server:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` in your browser. The API page is at
`http://127.0.0.1:8000/docs`.

In a second Termux session, send a report:

```sh
python contribute.py --server http://127.0.0.1:8000
```

## Let other people submit reports

The local address above only works on your phone. To accept reports from other
people, deploy the API to a host with HTTPS and persistent storage. Set
`CAPTCHA_FEEDBACK_DB` to a writable location on that host and back up the SQLite
database regularly.

The built-in rate limiter is intended for a small, single-process deployment. It
keeps temporary counters in memory, so the counters reset when the server restarts
and are not shared between multiple workers. For a larger public deployment, use
rate limiting at the hosting proxy or a shared store such as Redis.

## View the results

Open `/api/stats`. It shows the number of reports for each category and a table
comparing detector labels with the categories people submitted.

The reported match rate is only a rough community metric. Reports are not independently
verified, so it should not be presented as a tested model-accuracy score. This version
collects data; it does not train or update a machine-learning model.

## Main files

- `server.py` — FastAPI app and SQLite storage.
- `contribute.py` — command-line form for submitting a report.
- `requirements.txt` — Python packages.
