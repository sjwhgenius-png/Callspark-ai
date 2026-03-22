from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from supabase import Client, create_client
from twilio.rest import Client as TwilioClient


app = FastAPI(title="CallSpark AI Backend", version="0.1.0")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


# Lazy clients so local dev can start without every key.
_openai_client: Optional[OpenAI] = None
_supabase_client: Optional[Client] = None
_twilio_client: Optional[TwilioClient] = None


def get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=env("OPENAI_API_KEY"))
    return _openai_client



def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"))
    return _supabase_client



def get_twilio() -> TwilioClient:
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = TwilioClient(env("TWILIO_ACCOUNT_SID"), env("TWILIO_AUTH_TOKEN"))
    return _twilio_client


@dataclass
class BusinessConfig:
    id: str
    business_name: str
    service_area: List[str]
    business_hours: str
    booking_link: Optional[str]
    escalation_phone: Optional[str]
    tone: str
    emergency_rules: List[str]
    from_phone: Optional[str] = None


class WebformPayload(BaseModel):
    business_id: str
    name: Optional[str] = None
    phone: str
    service_type: Optional[str] = None
    issue_summary: Optional[str] = None
    suburb: Optional[str] = None
    notes: Optional[str] = None


class QualifyRequest(BaseModel):
    business_id: str
    lead_id: Optional[str] = None
    channel: str = Field(description="sms, webform, or voice")
    phone: Optional[str] = None
    latest_user_message: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


EMERGENCY_PATTERNS = {
    "gas_smell": re.compile(r"\bgas smell\b|\bsmell gas\b|\bgas leak\b", re.I),
    "burning_smell": re.compile(r"\bburning smell\b|\bburning\b.*\belectrical\b|\bsmoke\b", re.I),
    "no_cooling": re.compile(r"\bno cooling\b|\bac not cooling\b|\bair con.*not.*cold\b", re.I),
    "no_heating": re.compile(r"\bno heating\b|\bheater.*not.*work\b|\bfurnace.*not.*work\b", re.I),
    "water_leak": re.compile(r"\bleaking\b|\bwater leak\b|\bdripping\b", re.I),
}

STOP_PATTERNS = re.compile(r"^(stop|unsubscribe|cancel|end|quit)\b", re.I)
ANGRY_PATTERNS = re.compile(r"\bterrible\b|\bangry\b|\bcomplaint\b|\blawsuit\b|\brefund\b|\bidiot\b", re.I)


class RulesDecision(BaseModel):
    matched_emergency_rules: List[str] = Field(default_factory=list)
    emergency: bool = False
    outside_service_area: bool = False
    opted_out: bool = False
    angry_customer: bool = False
    should_escalate: bool = False
    escalation_reason: Optional[str] = None


class AiDecision(BaseModel):
    next_message: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    urgency: str = "normal"
    intent: str = "unknown"
    should_escalate: bool = False
    should_send_booking_link: bool = False
    closing_reason: Optional[str] = None


class AiResult(BaseModel):
    rules: RulesDecision
    ai: AiDecision


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "time": utc_now_iso()}


@app.post("/webhooks/twilio/voice-missed")
async def handle_missed_call(request: Request) -> JSONResponse:
    form = await request.form()
    from_phone = (form.get("From") or "").strip()
    to_phone = (form.get("To") or os.getenv("TWILIO_PHONE_NUMBER", "")).strip()
    business = get_business_by_phone(to_phone)
    if not from_phone:
        raise HTTPException(status_code=400, detail="Missing caller phone")

    lead = upsert_lead(
        business_id=business.id,
        phone=from_phone,
        source="missed_call",
        status="new",
    )
    log_message(lead["id"], "inbound", "voice", "MISSED_CALL")

    first_message = f"Hi, this is {business.business_name}. Sorry we missed your call. Are you needing HVAC repair, installation, maintenance, or something else?"
    send_sms(to_phone=from_phone, from_phone=to_phone or env("TWILIO_PHONE_NUMBER"), body=first_message)
    log_message(lead["id"], "outbound", "sms", first_message)
    update_lead(lead["id"], {"status": "contacted", "last_contact_at": utc_now_iso()})

    return JSONResponse({"ok": True, "lead_id": lead["id"], "message_sent": True})


@app.post("/webhooks/twilio/sms")
async def handle_inbound_sms(request: Request) -> JSONResponse:
    form = await request.form()
    from_phone = (form.get("From") or "").strip()
    to_phone = (form.get("To") or os.getenv("TWILIO_PHONE_NUMBER", "")).strip()
    body = (form.get("Body") or "").strip()
    if not from_phone or not body:
        raise HTTPException(status_code=400, detail="Missing From or Body")

    business = get_business_by_phone(to_phone)
    lead = upsert_lead(business_id=business.id, phone=from_phone, source="sms", status="active")
    log_message(lead["id"], "inbound", "sms", body)

    history = get_conversation_history(lead["id"])
    result = run_qualifier(
        business=business,
        channel="sms",
        latest_user_message=body,
        conversation_history=history,
        phone=from_phone,
    )

    apply_extracted_fields(lead["id"], result.ai.extracted_fields)

    if result.rules.opted_out:
        update_lead(lead["id"], {"status": "opted_out", "outcome": "sms_stop"})
        return JSONResponse({"ok": True, "opted_out": True})

    if result.rules.should_escalate or result.ai.should_escalate:
        escalate_lead(lead["id"], business, body, result)
        msg = (
            f"Thanks — I’m flagging this for the {business.business_name} team now. "
            "A human will follow up as soon as possible."
        )
        send_sms(from_phone=to_phone or env("TWILIO_PHONE_NUMBER"), to_phone=from_phone, body=msg)
        log_message(lead["id"], "outbound", "sms", msg)
        update_lead(lead["id"], {"status": "escalated", "outcome": result.rules.escalation_reason or "ai_escalation"})
        return JSONResponse({"ok": True, "escalated": True, "lead_id": lead["id"]})

    outbound = result.ai.next_message
    if result.ai.should_send_booking_link and business.booking_link:
        outbound = (
            (outbound + " " if outbound else "")
            + f"You can request a time here: {business.booking_link}"
        )

    if outbound:
        send_sms(from_phone=to_phone or env("TWILIO_PHONE_NUMBER"), to_phone=from_phone, body=outbound)
        log_message(lead["id"], "outbound", "sms", outbound)

    update_lead(
        lead["id"],
        {
            "status": "active",
            "urgency": result.ai.urgency,
            "last_contact_at": utc_now_iso(),
        },
    )
    return JSONResponse({"ok": True, "lead_id": lead["id"], "result": result.model_dump()})


@app.post("/webhooks/webform")
def handle_webform(payload: WebformPayload) -> JSONResponse:
    business = get_business(payload.business_id)
    lead = upsert_lead(
        business_id=payload.business_id,
        phone=payload.phone,
        source="webform",
        status="new",
        defaults={
            "customer_name": payload.name,
            "service_type": payload.service_type,
            "issue_summary": payload.issue_summary or payload.notes,
            "suburb": payload.suburb,
        },
    )

    summary = payload.issue_summary or payload.notes or payload.service_type or "Website inquiry"
    log_message(lead["id"], "inbound", "webform", summary)

    first_message = (
        f"Hi, this is {business.business_name}. Thanks for reaching out. "
        "I can help collect the details now so our team can follow up quickly. Is this an emergency?"
    )
    send_sms(from_phone=business.from_phone or env("TWILIO_PHONE_NUMBER"), to_phone=payload.phone, body=first_message)
    log_message(lead["id"], "outbound", "sms", first_message)
    update_lead(lead["id"], {"status": "contacted", "last_contact_at": utc_now_iso()})
    return JSONResponse({"ok": True, "lead_id": lead["id"]})


@app.post("/internal/qualify")
def internal_qualify(payload: QualifyRequest) -> Dict[str, Any]:
    business = get_business(payload.business_id)
    result = run_qualifier(
        business=business,
        channel=payload.channel,
        latest_user_message=payload.latest_user_message,
        conversation_history=payload.conversation_history,
        phone=payload.phone,
    )
    return result.model_dump()


@app.post("/internal/report/daily")
def daily_report() -> Dict[str, Any]:
    supabase = get_supabase()
    today = datetime.now(timezone.utc).date().isoformat()
    leads_resp = (
        supabase.table("leads")
        .select("id,source,status,outcome,urgency,created_at")
        .gte("created_at", f"{today}T00:00:00+00:00")
        .execute()
    )
    leads = leads_resp.data or []

    summary = {
        "date": today,
        "new_leads": len(leads),
        "sources": {},
        "statuses": {},
        "urgent": 0,
    }
    for lead in leads:
        summary["sources"][lead.get("source", "unknown")] = summary["sources"].get(lead.get("source", "unknown"), 0) + 1
        summary["statuses"][lead.get("status", "unknown")] = summary["statuses"].get(lead.get("status", "unknown"), 0) + 1
        if lead.get("urgency") in {"high", "emergency"}:
            summary["urgent"] += 1

    return {"ok": True, "summary": summary}


# ---------- Business / Storage helpers ----------

def get_business(business_id: str) -> BusinessConfig:
    supabase = get_supabase()
    resp = supabase.table("businesses").select("*").eq("id", business_id).limit(1).execute()
    rows = resp.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Business not found")
    return normalize_business(rows[0])



def get_business_by_phone(to_phone: str) -> BusinessConfig:
    supabase = get_supabase()
    query_phone = normalize_phone(to_phone)
    resp = supabase.table("businesses").select("*").eq("from_phone", query_phone).limit(1).execute()
    rows = resp.data or []
    if rows:
        return normalize_business(rows[0])

    fallback_id = os.getenv("DEFAULT_BUSINESS_ID")
    if fallback_id:
        return get_business(fallback_id)
    raise HTTPException(status_code=404, detail="Business not found for phone number")



def normalize_business(row: Dict[str, Any]) -> BusinessConfig:
    return BusinessConfig(
        id=row["id"],
        business_name=row["business_name"],
        service_area=row.get("service_area") or [],
        business_hours=row.get("business_hours") or "Mon-Fri 8am-6pm",
        booking_link=row.get("booking_link"),
        escalation_phone=row.get("escalation_phone"),
        tone=row.get("tone") or "friendly, concise, professional",
        emergency_rules=row.get("emergency_rules") or [],
        from_phone=row.get("from_phone"),
    )



def upsert_lead(
    business_id: str,
    phone: str,
    source: str,
    status: str,
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    defaults = defaults or {}
    supabase = get_supabase()
    clean_phone = normalize_phone(phone)
    existing = (
        supabase.table("leads")
        .select("*")
        .eq("business_id", business_id)
        .eq("phone", clean_phone)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if rows:
        return rows[0]

    payload = {
        "business_id": business_id,
        "phone": clean_phone,
        "source": source,
        "status": status,
        "created_at": utc_now_iso(),
        **{k: v for k, v in defaults.items() if v is not None},
    }
    inserted = supabase.table("leads").insert(payload).execute()
    return inserted.data[0]



def update_lead(lead_id: str, patch: Dict[str, Any]) -> None:
    get_supabase().table("leads").update(patch).eq("id", lead_id).execute()



def apply_extracted_fields(lead_id: str, fields: Dict[str, Any]) -> None:
    allowed = {
        "customer_name",
        "service_type",
        "issue_summary",
        "urgency",
        "suburb",
        "existing_customer",
        "callback_preference",
        "booking_intent_status",
    }
    patch = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if patch:
        update_lead(lead_id, patch)



def log_message(lead_id: str, direction: str, channel: str, body: str) -> None:
    get_supabase().table("messages").insert(
        {
            "lead_id": lead_id,
            "direction": direction,
            "channel": channel,
            "body": body,
            "created_at": utc_now_iso(),
        }
    ).execute()



def get_conversation_history(lead_id: str) -> List[Dict[str, str]]:
    resp = (
        get_supabase()
        .table("messages")
        .select("direction,body")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .execute()
    )
    history = []
    for msg in resp.data or []:
        role = "assistant" if msg["direction"] == "outbound" else "user"
        history.append({"role": role, "content": msg["body"]})
    return history


# ---------- Rules / AI ----------

def run_qualifier(
    business: BusinessConfig,
    channel: str,
    latest_user_message: str,
    conversation_history: List[Dict[str, str]],
    phone: Optional[str] = None,
) -> AiResult:
    rules = evaluate_rules(business, latest_user_message)
    if rules.opted_out:
        return AiResult(
            rules=rules,
            ai=AiDecision(
                next_message=None,
                extracted_fields={},
                urgency="normal",
                intent="opt_out",
                should_escalate=False,
                should_send_booking_link=False,
                closing_reason="opt_out",
            ),
        )

    ai = call_openai_qualifier(business, channel, latest_user_message, conversation_history, rules, phone)
    return AiResult(rules=rules, ai=ai)



def evaluate_rules(business: BusinessConfig, latest_user_message: str) -> RulesDecision:
    msg = latest_user_message or ""
    matched: List[str] = []
    for name, pattern in EMERGENCY_PATTERNS.items():
        if pattern.search(msg):
            matched.append(name)

    emergency = bool(matched)
    opted_out = bool(STOP_PATTERNS.search(msg.strip()))
    angry = bool(ANGRY_PATTERNS.search(msg))

    outside_service_area = False
    if business.service_area:
        msg_lower = msg.lower()
        if any(token.isdigit() and len(token) >= 4 for token in re.findall(r"\b\d{4,5}\b", msg_lower)):
            codes = set(re.findall(r"\b\d{4,5}\b", msg_lower))
            if not any(area in codes for area in business.service_area if area.isdigit()):
                outside_service_area = True

    should_escalate = emergency or angry
    reason = None
    if "gas_smell" in matched or "burning_smell" in matched:
        should_escalate = True
        reason = "dangerous_issue"
    elif angry:
        reason = "angry_customer"
    elif emergency:
        reason = "emergency_issue"
    elif outside_service_area:
        reason = "outside_service_area"

    return RulesDecision(
        matched_emergency_rules=matched,
        emergency=emergency,
        outside_service_area=outside_service_area,
        opted_out=opted_out,
        angry_customer=angry,
        should_escalate=should_escalate,
        escalation_reason=reason,
    )



def call_openai_qualifier(
    business: BusinessConfig,
    channel: str,
    latest_user_message: str,
    conversation_history: List[Dict[str, str]],
    rules: RulesDecision,
    phone: Optional[str],
) -> AiDecision:
    client = get_openai()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    system = f"""
You are CallSpark AI, the front-line receptionist for an HVAC company.
Your job is to help new inbound leads quickly.
Be concise, helpful, and professional.
Ask only one question at a time.
Never invent pricing, technician availability, or technical advice.
Never promise a confirmed booking unless the booking system confirms it.
If the issue sounds dangerous, urgent, outside service area, or outside policy, set should_escalate=true.
Your goal is to collect the minimum information needed to route or book the lead.

Business rules:
- Business name: {business.business_name}
- Service area: {json.dumps(business.service_area)}
- Business hours: {business.business_hours}
- Emergency jobs: {json.dumps(business.emergency_rules)}
- Escalation contact: {business.escalation_phone}
- Booking link: {business.booking_link}
- Tone: {business.tone}

Required fields to collect when possible:
- customer_name
- service_type
- issue_summary
- urgency
- suburb
- existing_customer
- callback_preference
- booking_intent_status

Return valid JSON only with keys:
next_message, extracted_fields, urgency, intent, should_escalate, should_send_booking_link, closing_reason
""".strip()

    messages = conversation_history[-12:] + [{"role": "user", "content": latest_user_message}]

    user_payload = {
        "channel": channel,
        "phone": phone,
        "latest_user_message": latest_user_message,
        "rules_precheck": rules.model_dump(),
        "conversation_history": messages,
    }

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
    )

    text = extract_output_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Model did not return valid JSON: {text}") from exc

    return AiDecision(**data)



def extract_output_text(response: Any) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text
    if hasattr(response, "output"):
        parts: List[str] = []
        for item in response.output:
            content = getattr(item, "content", None) or []
            for c in content:
                txt = getattr(c, "text", None)
                if txt:
                    parts.append(txt)
        if parts:
            return "".join(parts)
    raise HTTPException(status_code=500, detail="Unable to read model response")


# ---------- Integrations ----------

def send_sms(*, from_phone: str, to_phone: str, body: str) -> None:
    get_twilio().messages.create(from_=from_phone, to=normalize_phone(to_phone), body=body)



def escalate_lead(lead_id: str, business: BusinessConfig, latest_user_message: str, result: AiResult) -> None:
    if not business.escalation_phone:
        return
    body = (
        f"RecallFlow escalation for {business.business_name}\n"
        f"Lead ID: {lead_id}\n"
        f"Reason: {result.rules.escalation_reason or 'ai_escalation'}\n"
        f"User message: {latest_user_message}\n"
        f"Extracted: {json.dumps(result.ai.extracted_fields)}"
    )
    send_sms(
        from_phone=business.from_phone or env("TWILIO_PHONE_NUMBER"),
        to_phone=business.escalation_phone,
        body=body,
    )



def normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+"):
        return digits
    if digits.startswith("1") and len(digits) == 11:
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    return digits
