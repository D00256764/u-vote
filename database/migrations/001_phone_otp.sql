-- Migration 001: Replace DOB-based MFA with phone OTP
--
-- Changes:
--   1. voters: add phone_number, drop date_of_birth
--   2. voter_mfa: add otp_code + otp_expires_at columns
--
-- Run order: apply AFTER init.sql (first-time setup already done)

-- Step 1: Add phone number to voters
ALTER TABLE voters ADD COLUMN phone_number VARCHAR(20);

-- Step 2: Drop DOB (no longer used for MFA)
ALTER TABLE voters DROP COLUMN date_of_birth;

-- Step 3: Add OTP columns to voter_mfa
ALTER TABLE voter_mfa
    ADD COLUMN otp_code       VARCHAR(6),
    ADD COLUMN otp_expires_at TIMESTAMP;
