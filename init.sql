CREATE TABLE IF NOT EXISTS service_cases (
    id SERIAL PRIMARY KEY,
    case_id TEXT UNIQUE NOT NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    vehicle_make TEXT NOT NULL,
    vehicle_model TEXT NOT NULL,
    vehicle_year INTEGER,
    vin TEXT,
    symptom_description TEXT NOT NULL,
    issue_category TEXT NOT NULL,
    affected_system TEXT NOT NULL,
    urgency TEXT NOT NULL,
    ai_summary TEXT NOT NULL,
    technician_skill TEXT NOT NULL,
    required_parts JSONB NOT NULL,
    warranty_active BOOLEAN,
    warranty_status TEXT NOT NULL,
    requires_human_review BOOLEAN NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS technicians (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    skills TEXT NOT NULL,
    availability_status TEXT NOT NULL DEFAULT 'available',
    location TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parts_inventory (
    id SERIAL PRIMARY KEY,
    part_name TEXT NOT NULL UNIQUE,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    warehouse_location TEXT NOT NULL
);

ALTER TABLE service_cases
    ADD COLUMN IF NOT EXISTS matched_technician_id INTEGER,
    ADD COLUMN IF NOT EXISTS parts_available BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    case_id TEXT NOT NULL UNIQUE,
    technician_id INTEGER REFERENCES technicians(id),
    proposed_start TIMESTAMPTZ NOT NULL,
    proposed_end TIMESTAMPTZ NOT NULL,
    sla_due_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    case_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO technicians (id, name, skills, availability_status, location)
VALUES
    (1, 'Amit Sharma', 'Certified EV high-voltage technician, BMS diagnostics', 'available', 'Mumbai Service Centre'),
    (2, 'Priya Mehta', 'Infotainment and vehicle electronics technician', 'available', 'Delhi Service Centre'),
    (3, 'Rahul Verma', 'General automotive technician, brakes and suspension', 'busy', 'Pune Service Centre')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parts_inventory (part_name, stock_quantity, warehouse_location)
VALUES
    ('Battery Management System (BMS) module', 3, 'Mumbai Warehouse'),
    ('High-voltage battery pack (replacement)', 0, 'Mumbai Warehouse'),
    ('HV contactor/relay', 5, 'Mumbai Warehouse'),
    ('Battery cooling system components (coolant pump/hoses)', 0, 'Mumbai Warehouse'),
    ('Infotainment head unit', 2, 'Delhi Warehouse')
ON CONFLICT (part_name) DO NOTHING;
