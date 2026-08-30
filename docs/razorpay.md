# Razorpay Integration

## REAL vs SIMULATED, precisely

Per the spec's explicit requirement, this distinction is drawn as
sharply as possible and stated here without hedging.

### Genuinely verified against live Razorpay behavior

- **Webhook signature scheme**: `X-Razorpay-Signature` header,
  HMAC-SHA256 keyed with the webhook secret, computed over the **raw**
  request body (never the parsed/re-serialized JSON). Confirmed by
  fetching `https://razorpay.com/docs/webhooks/validate-test/`
  directly before writing any code.
- **`payment.failed` webhook payload shape**: `payload.payment.entity`
  containing `id`, `amount`, `currency`, `status`, `method`,
  `customer_id`, `error_code`, `error_description`, confirmed against
  official Razorpay documentation.
- **`x-razorpay-event-id` header** for deduplication, confirmed from
  docs.
- **The HMAC verification logic itself is genuinely tested** against
  the real algorithm end-to-end: valid signature accepted, tampered
  body rejected, tampered signature rejected, wrong secret rejected,
  missing signature rejected (`tests/security/test_webhook_signature.py`,
  6 tests) -- this part required no live Razorpay traffic to verify
  correctly, since it's pure HMAC math.

### NOT verified -- built against documentation, never exercised live

- **No live Razorpay test-mode account or API credentials** were
  available in the build environment. `api.razorpay.com` is not
  reachable from the sandbox network allowlist either.
- `RazorpayClientWrapper`'s `REAL_RAZORPAY` methods (`fetch_payment`,
  `create_payment_link`, `fetch_subscription`, `fetch_invoice`) are
  implemented against the documented `razorpay` Python SDK interface
  (confirmed the package exists and its `Client(auth=(key_id,
  key_secret))` pattern via `pip install razorpay` + SDK source
  inspection) but have never been called against a real account.
- **Real webhook traffic from Razorpay's servers** was never received
  -- only self-constructed test payloads matching the documented
  shape were used.

### Only one event type is mapped

`app/webhooks/razorpay_parser.py` maps **only** `payment.failed` to
the internal taxonomy. Other event types Razorpay's docs index lists
(`subscription.*`, `invoice.*`, `payment.captured`,
`payment.authorized`) exist but their exact payload shapes were not
fetched and confirmed in this build. Rather than guess at field
names, unmapped events are **acknowledged** (HTTP 200, so Razorpay
doesn't retry-storm the endpoint) with `mapped: false` in the
response -- never silently misparsed. Verified in
`tests/integration/test_razorpay_webhook.py::test_webhook_unmapped_event_type_is_acknowledged_not_guessed`.

## SIMULATED_RAZORPAY mode

The only mode actually exercised in this build. Every simulated
response includes `"simulated": true` explicitly. The dashboard
badges every simulated row visibly (`SimulationBadge` component,
`REAL` vs `SIMULATED`).

`CREATE_PAYMENT_LINK` (Phase 11's execution simulator) genuinely calls
`RazorpayClientWrapper.create_payment_link()` -- the simulated-link
code path is real, executed code, not an inline stand-in written
directly in the simulator.

## Switching to REAL_RAZORPAY

Set `RAZORPAY_MODE=test` (or `live`) and provide
`RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET`/`RAZORPAY_WEBHOOK_SECRET` in
`.env`. `RazorpayClientWrapper` will then route calls through the real
SDK. **This has not been tested** -- if you do this, please verify the
SDK calls actually work against your account, since the code was
written against documentation, not live behavior.
