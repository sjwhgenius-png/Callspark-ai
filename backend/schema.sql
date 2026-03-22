create extension if not exists pgcrypto;

create table if not exists businesses (
  id uuid primary key default gen_random_uuid(),
  business_name text not null,
  from_phone text unique,
  business_hours text,
  service_area jsonb not null default '[]'::jsonb,
  booking_link text,
  escalation_phone text,
  tone text,
  emergency_rules jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  created_at timestamptz not null default now(),
  last_contact_at timestamptz,
  source text not null,
  status text not null,
  outcome text,
  phone text not null,
  customer_name text,
  service_type text,
  issue_summary text,
  urgency text,
  suburb text,
  existing_customer boolean,
  callback_preference text,
  booking_intent_status text,
  assigned_to text
);

create index if not exists idx_leads_business_phone on leads(business_id, phone);
create index if not exists idx_leads_created_at on leads(created_at desc);

create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads(id) on delete cascade,
  direction text not null,
  channel text not null,
  body text not null,
  model_used text,
  created_at timestamptz not null default now()
);

create index if not exists idx_messages_lead_created_at on messages(lead_id, created_at asc);

create table if not exists events (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references leads(id) on delete cascade,
  event_type text not null,
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

insert into businesses (
  business_name,
  from_phone,
  business_hours,
  service_area,
  booking_link,
  escalation_phone,
  tone,
  emergency_rules
)
values (
  'Northwind HVAC',
  '+15551234567',
  'Mon-Fri 8am-6pm; Sat 9am-1pm',
  '["78701", "78702", "78703", "78704", "78705"]'::jsonb,
  'https://example.com/book',
  '+15557654321',
  'friendly, concise, professional',
  '["gas smell", "burning smell", "no cooling", "no heating", "water leak"]'::jsonb
)
on conflict (from_phone) do nothing;
