# Crypto Bag Tracker - Security & Compliance Documentation

## Overview

This document outlines the security measures, data handling practices, and compliance standards implemented by Crypto Bag Tracker. It is intended for insurance underwriters, auditors, and compliance officers.

---

## 1. Security Architecture

### 1.1 Infrastructure Security

| Layer | Technology | Security Measure |
|-------|------------|------------------|
| Transport | HTTPS/TLS 1.3 | All data encrypted in transit |
| Application | FastAPI | Input validation, CORS protection |
| Database | MongoDB Atlas | Encryption at rest, network isolation |
| Hosting | Render | SOC 2 compliant infrastructure |

### 1.2 Authentication & Authorization

| Control | Implementation |
|---------|----------------|
| Password Storage | bcrypt hashing (8 rounds) |
| Session Management | JWT tokens (24-hour expiry) |
| Access Control | Role-based (Free vs Unlimited tier) |
| API Authentication | Bearer token required |

### 1.3 Data Encryption

| Data Type | Encryption Method | Key Management |
|-----------|-------------------|----------------|
| Passwords | bcrypt hash | One-way hash, not reversible |
| API Keys | Fernet (AES-128-CBC) | Environment variable |
| OAuth Tokens | Fernet (AES-128-CBC) | Environment variable |
| Database | MongoDB Atlas TLS | Managed by MongoDB |

### 1.4 Application Security

- **Input Validation:** All user inputs validated and sanitized
- **SQL Injection:** N/A (NoSQL database)
- **XSS Protection:** React auto-escapes output
- **CSRF Protection:** Token-based authentication
- **Rate Limiting:** Per-endpoint limits to prevent abuse

---

## 2. Data Handling Practices

### 2.1 Data Collection

We collect the following user data:

| Data Type | Purpose | Retention |
|-----------|---------|-----------|
| Email Address | Account identification, communication | Account lifetime |
| Password Hash | Authentication | Account lifetime |
| Wallet Addresses | Portfolio analysis | User-controlled |
| Transaction Data | Tax calculations | User-controlled |
| Exchange API Keys | Exchange integration | User-controlled, encrypted |
| Payment Info | Subscription billing | Managed by Stripe |

### 2.2 Data We Do NOT Collect

- Private keys or seed phrases
- Social Security Numbers
- Bank account information
- Government-issued ID
- Biometric data

### 2.3 Data Storage

| Data | Location | Encryption |
|------|----------|------------|
| User Accounts | MongoDB Atlas (AWS) | At rest + in transit |
| API Keys | MongoDB Atlas | AES-128 encrypted |
| Payment Data | Stripe (PCI compliant) | Stripe managed |
| Session Data | JWT (client-side) | Signed tokens |

### 2.4 Data Sharing

We do NOT share user data with third parties except:

| Third Party | Purpose | Data Shared |
|-------------|---------|-------------|
| Stripe | Payment processing | Email, subscription status |
| MongoDB Atlas | Database hosting | All application data (encrypted) |
| Render | Application hosting | Application logs |

### 2.5 Data Retention & Deletion

- Users can delete their account at any time
- Account deletion removes all associated data
- Backups retained for 30 days for disaster recovery
- No data sold to third parties

---

## 3. Access Controls

### 3.1 Production Access

| Access Type | Personnel | Controls |
|-------------|-----------|----------|
| Database (Read/Write) | Engineering Lead | SSH key + IP whitelist |
| Database (Read Only) | Support Team | Limited credentials |
| Application Logs | Engineering Team | Render dashboard access |
| Stripe Dashboard | Finance/Admin | 2FA required |

### 3.2 User Access Controls

| Feature | Free Tier | Unlimited Tier |
|---------|-----------|----------------|
| Wallet Analysis | 1 total | Unlimited |
| Tax Reports | No | Yes |
| Exchange Import | No | Yes |
| Chain of Custody | No | Yes |
| API Key Storage | No | Yes (encrypted) |

### 3.3 Exchange API Permissions

All exchange connections use **READ-ONLY** API permissions:

| Exchange | Permissions Required |
|----------|---------------------|
| Coinbase | wallet:accounts:read, wallet:transactions:read |
| Binance | Read-only API key |
| Kraken | Query funds permission only |
| All Others | Read-only API access |

**Critical:** Our application CANNOT:
- Move, send, or withdraw funds
- Execute trades
- Modify account settings
- Access withdrawal addresses

---

## 4. Compliance Standards

### 4.1 Financial Data

| Standard | Status | Notes |
|----------|--------|-------|
| PCI DSS | Compliant via Stripe | No card data stored |
| SOX | N/A | Not publicly traded |
| GLBA | Partial | Tax software exemption |

### 4.2 Privacy Regulations

| Regulation | Status | Implementation |
|------------|--------|----------------|
| CCPA | Compliant | Data deletion, disclosure |
| GDPR | Compliant | Data portability, deletion |
| COPPA | N/A | No users under 13 |

### 4.3 Tax Compliance

| Requirement | Implementation |
|-------------|----------------|
| FIFO Method | IRS-accepted cost basis calculation |
| Form 8949 | Standard CSV format for import |
| Schedule D | Summary totals provided |
| Record Keeping | Transaction history exportable |

---

## 5. Incident Response

### 5.1 Incident Classification

| Severity | Definition | Response Time |
|----------|------------|---------------|
| Critical | Data breach, service down | 1 hour |
| High | Security vulnerability | 4 hours |
| Medium | Feature malfunction | 24 hours |
| Low | Minor bug | 72 hours |

### 5.2 Incident Response Process

1. **Detection** - Monitoring alerts, user reports
2. **Triage** - Classify severity, assign owner
3. **Containment** - Isolate affected systems
4. **Investigation** - Root cause analysis
5. **Remediation** - Fix and deploy
6. **Communication** - Notify affected users
7. **Post-Mortem** - Document lessons learned

### 5.3 Breach Notification

In the event of a data breach:
- Affected users notified within 72 hours
- State attorneys general notified as required
- Detailed incident report prepared
- Credit monitoring offered if applicable

---

## 6. Business Continuity

### 6.1 Backup Strategy

| Data | Frequency | Retention | Location |
|------|-----------|-----------|----------|
| Database | Continuous | 30 days | MongoDB Atlas |
| Code | Every commit | Indefinite | GitHub |
| Config | Daily | 90 days | Encrypted storage |

### 6.2 Disaster Recovery

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Database failure | 1 hour | 1 hour | MongoDB failover |
| Application crash | 15 min | 0 | Render auto-restart |
| Region outage | 4 hours | 1 hour | Cross-region restore |
| Complete loss | 24 hours | 24 hours | Full rebuild from backups |

### 6.3 Uptime Commitment

- Target Availability: 99.5%
- Maintenance Windows: Sundays 2-4 AM EST
- Status Page: [To be implemented]

---

## 7. Third-Party Security

### 7.1 Vendor Assessment

| Vendor | Purpose | Security Certification |
|--------|---------|----------------------|
| Render | Hosting | SOC 2 Type II |
| MongoDB Atlas | Database | SOC 2 Type II, ISO 27001 |
| Stripe | Payments | PCI DSS Level 1 |
| GitHub | Code Repository | SOC 2 Type II |
| Alchemy | Blockchain API | SOC 2 Type II |

### 7.2 API Security

| API | Authentication | Rate Limits |
|-----|----------------|-------------|
| Alchemy | API Key | 330 req/sec |
| CoinGecko | None (public) | 10-50 req/min |
| Stripe | Secret Key | Standard limits |
| Coinbase | OAuth 2.0 | Per-endpoint |

---

## 8. Audit Trail

### 8.1 Logged Events

| Event | Data Captured |
|-------|---------------|
| Login | Timestamp, IP, success/failure |
| Wallet Analysis | Timestamp, address, chain |
| Export Generated | Timestamp, type, user |
| Subscription Change | Timestamp, old/new tier |
| API Key Added | Timestamp, exchange (not key) |

### 8.2 Log Retention

- Application Logs: 30 days
- Security Logs: 90 days
- Audit Logs: 1 year

---

## 9. Security Testing

### 9.1 Testing Schedule

| Test Type | Frequency | Last Performed |
|-----------|-----------|----------------|
| Dependency Scan | Weekly (automated) | Ongoing |
| Code Review | Every PR | Ongoing |
| Penetration Test | Annually | Not yet |
| Security Audit | Annually | Not yet |

### 9.2 Vulnerability Management

- Dependencies monitored via GitHub Dependabot
- Critical vulnerabilities patched within 24 hours
- High vulnerabilities patched within 7 days

---

## 10. Insurance Considerations

### 10.1 Risk Profile

| Risk Category | Level | Mitigation |
|---------------|-------|------------|
| Data Breach | Medium | Encryption, access controls |
| Service Outage | Low | Cloud hosting, auto-scaling |
| Financial Loss | Low | Read-only access, no fund control |
| Regulatory Fine | Low | Compliance measures in place |

### 10.2 Coverage Recommendations

| Coverage Type | Recommended |
|---------------|-------------|
| Cyber Liability | Yes |
| E&O / Professional Liability | Yes |
| General Liability | Yes |
| D&O | If applicable |

### 10.3 Key Risk Mitigations

1. **No Fund Control** - Application cannot move cryptocurrency
2. **Read-Only Access** - All exchange connections are read-only
3. **No Private Keys** - We never store or request private keys
4. **Encrypted Storage** - Sensitive data encrypted at rest
5. **Established Infrastructure** - Using proven cloud providers

---

## 11. Contact Information

**Security Issues:** [security@cryptobagtracker.io]  
**Compliance Inquiries:** [compliance@cryptobagtracker.io]  
**General Support:** [support@cryptobagtracker.io]

---

## 12. Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Mar 10, 2026 | Product Team | Initial version |

---

*This document is confidential and intended for insurance underwriters, auditors, and compliance officers evaluating Crypto Bag Tracker.*
