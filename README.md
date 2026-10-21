# M-Pesa STK Push Helper

A small FastAPI service that sends M-Pesa STK Push payment prompts through Safaricom's Daraja sandbox and records the result when Safaricom calls back.

It handles all the parts of Daraja for you: access tokens, the STK password and timestamp, phone number formats, and callback parsing.

📖 **Documentation:** _add Thally site URL here_

## Quickstart (mock mode, no Safaricom account needed)

Requires Python 3.10 or later.

```bash
git clone <your-repo-url>
cd mpesa-stk-helper
python3 -m venv virtual
source virtual/bin/activate      
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Send a payment prompt:

```bash
curl -X POST http://127.0.0.1:8000/stk-push \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "0712345678", "amount": 1}'
```

You'll get a `checkout_request_id` with status `pending`. To try it in the browser instead, open http://127.0.0.1:8000/docs.

## Simulate Safaricom's callback

Replace `REPLACE_ME` in `samples/callback.json` with your `checkout_request_id`, then:

```bash
curl -X POST http://127.0.0.1:8000/callback/change-me \
  -H "Content-Type: application/json" -d @samples/callback.json
curl http://127.0.0.1:8000/payments/<checkout_request_id>
```

The status is now `completed`, with receipt number `SAMPLE1234`.

## Use the Daraja sandbox

1. Create an app on the Daraja developer portal and copy its consumer key and secret, plus the sandbox passkey.
2. Expose your server over HTTPS, for example with `ngrok http 8000`.
3. In `.env`, set `MOCK_MODE=false`, fill in the values, set `PUBLIC_BASE_URL` to your ngrok URL, and change `CALLBACK_SECRET` to a random value.

## Notes

Sandbox only. Payments are kept in memory and disappear when the server restarts. Never commit your `.env` file.