-- CV-15: Automated Election Windows
-- Adds optional scheduled open/close timestamps to elections.
-- If set, the APScheduler job in election-service will open/close automatically.
-- NULL means manual control only (existing behaviour unchanged).

ALTER TABLE elections
    ADD COLUMN scheduled_open_at  TIMESTAMP,
    ADD COLUMN scheduled_close_at TIMESTAMP;
