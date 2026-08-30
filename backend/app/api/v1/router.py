"""
Aggregates all v1 API routes. Later phases (webhooks, recovery-cases,
audit-logs, metrics, policies, evaluation, models) register their
routers here.
"""
from fastapi import APIRouter

from app.api.v1 import audit_logs, events, evaluation, health, metrics, models_performance, policies, recovery_cases
from app.webhooks import razorpay_webhook

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(events.router)
api_v1_router.include_router(razorpay_webhook.router)
api_v1_router.include_router(audit_logs.router)
api_v1_router.include_router(recovery_cases.router)
api_v1_router.include_router(evaluation.router)
api_v1_router.include_router(metrics.router)
api_v1_router.include_router(policies.router)
api_v1_router.include_router(models_performance.router)
