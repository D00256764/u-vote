#!/bin/bash
# Pre-bootstrap script for EKS managed nodes (u-vote).
# Runs before the standard EKS node bootstrap; keep changes minimal.
set -o errexit
set -o pipefail

# Ensure SSM agent is available for Session Manager debugging (Amazon Linux 2023).
if command -v dnf &>/dev/null; then
  dnf install -y amazon-ssm-agent || true
  systemctl enable amazon-ssm-agent || true
  systemctl start amazon-ssm-agent || true
fi
