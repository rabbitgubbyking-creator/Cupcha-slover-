# CAPTCHA Community Feedback

A small, privacy-conscious feedback service that helps a community measure how well a **challenge-type detector** categorizes CAPTCHA interfaces over time.

This is deliberately not a CAPTCHA solver. It does not recognize answers, submit responses, approve challenges, or bypass anti-bot checks.

## What improves over time

People can optionally report the broad category they saw and the category a detector displayed. The service aggregates these votes and builds a category confusion matrix. This helps maintainers see which categories are commonly misclassified and where a future, human-reviewed detector update is needed.

The current release collects feedback and analytics only. It does not train or update a model automatically.

## Privacy

The API stores only:
- The manually selected category.
- An optional detector category for comparison.
- The client version and timestamp.

It does **not** accept screenshots, CAPTCHA text, challenge answers, browser cookies, tokens, usernames, or account details. IP addresses are used transiently for rate limiting and are not stored in the database. Users should never submit private screenshots or account information.

## Run the API in Termux or on a server

Python 3.10 or newer is recommended.

```sh
pkg update
pkg install python
git clone https://github.com/rabbitgubbyking-creator/Cupcha-slover-.git
cd Cupcha-slover-
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` locally. API documentation is at `/docs`.

For multiple people to contribute, the API must be deployed on a server with persistent storage and an HTTPS URL. Do not expose a local development server directly to the public internet. Back up `data/feedback.sqlite3`.

## Submit feedback

In another Termux session:

```sh
python contribute.py --server http://127.0.0.1:8000
```

When using a hosted instance, replace the URL with its HTTPS address.

## View community stats

Open `/api/stats` on the server. It reports category totals, comparisons, and the observed match rate for human-reported predictions. This rate is descriptive and should not be treated as a validated accuracy score unless the feedback sample is reviewed for quality.

## API

- `GET /` — service status and privacy note.
- `GET /api/categories` — allowed categories.
- `POST /api/feedback` — submit one manually reviewed category.
- `GET /api/stats` — aggregate community metrics.

## License

No license has been added yet. Add a license before accepting outside contributions.
