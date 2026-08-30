def test_list_policies_returns_all_seeded_causes(api_client):
    resp = api_client.get("/api/v1/policies")
    assert resp.status_code == 200
    body = resp.json()
    causes = {item["cause"] for item in body["items"]}
    assert "insufficient_funds" in causes
    assert "risk_block" in causes
    assert len(body["items"]) == 11


def test_policy_entries_have_expected_fields(api_client):
    resp = api_client.get("/api/v1/policies")
    body = resp.json()
    risk_block = next(item for item in body["items"] if item["cause"] == "risk_block")
    assert risk_block["allowed_actions"] == ["ESCALATE_TO_HUMAN", "STOP_RECOVERY"]
    assert "RETRY_PAYMENT" in risk_block["blocked_actions"]
    assert risk_block["max_retries"] == 0


def test_models_performance_returns_real_metadata(api_client):
    resp = api_client.get("/api/v1/models/performance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cause_classifier"]["available"] is True
    assert body["cause_classifier"]["val_accuracy"] is not None
    assert len(body["cause_classifier"]["classes"]) == 11

    assert body["recovery_probability"]["available"] is True
    assert body["recovery_probability"]["val_roc_auc"] is not None
    assert body["recovery_probability"]["calibration_curve"] is not None
    assert len(body["recovery_probability"]["feature_importance"]) > 0
