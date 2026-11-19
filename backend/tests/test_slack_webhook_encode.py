from app.models.webhook import WebhookDelivery, WebhookEventType
from app.services.webhook_service import _encode_delivery_body, _is_slack_incoming_webhook


def test_slack_incoming_webhook_body_uses_text() -> None:
    assert _is_slack_incoming_webhook(
        "https://hooks.slack.com/services/T000/B000/XXX"
    )
    delivery = WebhookDelivery(
        organization_id="org-1",
        endpoint_id="ep-1",
        event_type=WebhookEventType.LEAD_CREATED,
        payload={
            "type": "lead.created",
            "data": {"lead_name": "Ada"},
        },
    )
    delivery.id = "del-1"
    body = _encode_delivery_body(
        "https://hooks.slack.com/services/T000/B000/XXX", delivery
    )
    assert b'"text":' in body
    assert b"Ada" in body
    assert b"flowpilot" in body
